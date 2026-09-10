"""`entrypoints.rest` exposes the `Agent` from a REST API.

This module defines a FastAPI app and endpoints that contain
the logic to interact with the `Agent` via HTTP requests.
It also defined a helper function to run the REST API using uvicorn.
"""

import json
import os
from collections.abc import AsyncGenerator

import httpx
import uvicorn
from ai_cost_optimizer.config import ExperimentConfig
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse

from rag.agent import Agent
from rag.config import settings

from .models import BaseModel, Messages

app = FastAPI()


class Data(BaseModel):
    """POST input data for the chat endpoint."""

    model: str
    messages: Messages
    # Phase 5: an optional per-request config override. Any field set here
    # takes precedence over the AI_OPTIMIZER_* env vars for this request
    # only - no container restart required. Fields left unset fall back to
    # the env vars (Phase 4b behavior, unchanged when this is omitted).
    config_override: ExperimentConfig | None = None


@app.get("/api/models")
async def get_models() -> JSONResponse:
    """Returns a list of available models."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{settings.chat_url}v1/model/info")
        body = response.json()

    model_list = [
        model["model_name"]
        for model in body["data"]
        if model["model_info"]["mode"] == "chat"
    ]
    return JSONResponse({"data": model_list})


@app.post("/api/chat")
async def send_messages(data: Data, stream: bool = False):  # noqa: ANN201
    """Receives a POST request with a JSON payload following the `Data` model.

    This function will reject the request if the payload does not conform to the `Data` model.

    Args:
        data (Data): The POST request payload; Must include `model` (str) and `messages` (Messages)
        stream (bool, optional): Query parameter; Whether to return the response as JSON (False) or SSE (True). Defaults to False.

    Returns:
        JSONResponse: If stream is False; A JSON response containing the generated text.
        StreamingResponse: If stream is True; A SSE response containing the generated text in data events.

    """
    agent = Agent(model=data.model, config_override=data.config_override)

    messages = data.messages.model_dump()

    async def full_response() -> AsyncGenerator[str]:
        # Agent.generate() returns after one LLM turn, which may end in a tool
        # call rather than real content (mirrors the CLI entrypoint's loop in
        # rag.entrypoints.cli, which re-invokes generate() while the last
        # message is a tool result).
        while True:
            async for chunk in agent.generate(messages):
                yield chunk
            if messages[-1]["role"] != "tool":
                break

    if stream:

        async def stream_response() -> AsyncGenerator[str]:
            async for chunk in full_response():
                yield f"data: {json.dumps(chunk)}\n\n"

        return StreamingResponse(stream_response())
    else:
        buffer = ""

        async for chunk in full_response():
            buffer += chunk

        # Phase 5: expose usage (token counts), summed across every LLM turn
        # this request drove (a tool call means more than one turn), so
        # callers that need real cost/quality numbers (the experiment
        # runner) don't have to guess. `None` when the underlying stream
        # didn't report usage (e.g. a provider that ignores
        # `stream_options.include_usage`).
        return JSONResponse({"response": buffer, "usage": agent.total_usage})


def api() -> None:  # pragma: no cover
    """Run the FastAPI app using uvicorn."""
    host = os.environ.get("HOST", "127.0.0.1")
    port = os.environ.get("PORT", "8000")

    uvicorn.run(app, host=host, port=int(port))

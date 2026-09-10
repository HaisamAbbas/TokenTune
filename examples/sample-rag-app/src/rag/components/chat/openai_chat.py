"""`chat.openai_chat` defines the OpenAIChat component.

This component uses the OpenAI API to generate chat completions.
It uses the AsyncOpenAI client to interact with the OpenAI API.
It exposes the following methods:
    - `generate_stream`: Generates a stream of chat completions.
"""

from typing import Any

from openai import AsyncOpenAI

from rag.types import Messages, Stream, Tool


class OpenAIChat:
    """OpenAIChat is an chat component that uses the OpenAI API to generate chat completions."""

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        _openai_client_class: type[AsyncOpenAI] = AsyncOpenAI,
    ) -> None:
        """Initialize an OpenAIChat instance.

        Args:
            api_key (str): The API key to use for authentication.
            base_url (str, optional): The base URL of the OpenAI API. Defaults to None.
            _openai_client_class (AsyncOpenAI, optional): The OpenAI client class to use. Defaults to AsyncOpenAI.

        """
        self.openai = _openai_client_class(api_key=api_key, base_url=base_url)

    async def generate_stream(
        self,
        messages: Messages,
        model: str,
        **kwargs: Any,
    ) -> Stream:
        """Generate a stream of chat completions.

        Args:
            messages (Iterable[ChatCompletionMessageParam]): The messages to generate the chat completions for.
            model (str): The model to use for the chat completions.
            **kwargs: Additional keyword arguments to pass to the OpenAI API.

        Returns:
            AsyncGenerator[StreamPart, None]: An asynchronous generator that yields the chat completions in chunks.

        """
        response = await self.openai.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            stream=True,
            # Ask the (litellm-proxied) API for a terminal usage-only chunk,
            # so callers get real token counts (Phase 5: needed by the
            # experiment runner to compute real cost/token metrics).
            stream_options={"include_usage": True},
            **kwargs,
        )

        tool_buffer_index: dict[int, Tool] = {}

        async for chunk in response:  # type: ignore[union-attr]
            # The usage chunk (when include_usage is honored) carries an
            # empty `choices` list - guard before indexing into it.
            if chunk.choices:
                delta = chunk.choices[0].delta
                if content := delta.content:
                    yield {"content": content, "tools": None, "usage": None}

                if tool_calls := delta.tool_calls:
                    for call in tool_calls:
                        idx = call.index
                        if idx not in tool_buffer_index:
                            tool_buffer_index[idx] = {
                                "id": "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            }
                        if call_id := call.id:
                            tool_buffer_index[idx]["id"] = call_id
                        if function := call.function:
                            if name := function.name:
                                tool_buffer_index[idx]["function"]["name"] = name
                            if arguments := function.arguments:
                                tool_buffer_index[idx]["function"]["arguments"] += arguments

            if usage := getattr(chunk, "usage", None):
                yield {
                    "content": None,
                    "tools": None,
                    "usage": {
                        "prompt_tokens": usage.prompt_tokens,
                        "completion_tokens": usage.completion_tokens,
                        "total_tokens": usage.total_tokens,
                    },
                }

        if tool_buffer_index:
            tool_buffers = list(tool_buffer_index.values())
            yield {"content": None, "tools": tool_buffers, "usage": None}

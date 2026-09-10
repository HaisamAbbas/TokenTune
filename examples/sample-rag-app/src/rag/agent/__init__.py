"""`rag.agent` defines the Agent class, which is the main logic abstraction for the application.

The main objective of the Agent class is to provide instructions to the AI through the system prompt and tool definitions,
along with access to components from the 'components' module in order to perform actions as needed.

An Agent instance uses components configured and provided by the 'config' module. It also imports the 'types' module for type-hinting.

The Agent class is what the entrypoints must import to interact with the application logic.
"""

import json
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from ai_cost_optimizer.client import OptimizerClient
from langfuse import get_client, observe

from rag import config
from rag.types import (
    AssistantMessage,
    Messages,
    OptionalChat,
    OptionalEmbed,
    OptionalSearch,
    SearchResult,
)

__all__ = ["Agent"]

agent_dir = Path(__file__).parent

system_prompt_txt = agent_dir / "system_prompt.txt"

tools_json = agent_dir / "tools.json"


class Agent:
    """`Agent` encapsulates a system prompt, tool definitions, and tool execution logic."""

    system = system_prompt_txt.read_text()
    tools = json.loads(tools_json.read_text())

    def __init__(
        self,
        model: str,
        _chat: OptionalChat = None,
        _search: OptionalSearch = None,
        _embed: OptionalEmbed = None,
    ) -> None:
        """Initialize an `Agent` instance.

        Args:
            model (str): The model to use for inference, as defined in the litellm config.
            _chat (OptionalChat, optional): The chat component to use to generate chat completions. Defaults to OpenAIChat if not provided.
            _search (OptionalSearch, optional): The search component to use to generate search results. Defaults to QdrantSearch if not provided.
            _embed (OptionalEmbed, optional): The embed component to use to generate embeddings. Defaults to OpenAIEmbed if not provided.

        """
        # AI Cost Optimizer config swap: any field the platform has an
        # opinion on (via AI_OPTIMIZER_* env vars, see OptimizerClient)
        # overrides the value the app/LLM would otherwise have used. A
        # field left None means "no opinion" - behavior is unchanged.
        self._optimizer_config = OptimizerClient(project_slug="sample-rag-app").get_config()

        self.model = self._optimizer_config.model or model
        self.system = self._optimizer_config.prompt or type(self).system
        self.chat = _chat or config.get_openai_chat()
        self.search = _search or config.get_qdrant()
        self.embed = _embed or config.get_openai_embed()

        self.tool_map = {
            "hybrid_search": self._hybrid_search_pipeline,
            "semantic_search": self._semantic_search_pipeline,
            "keyword_search": self._keyword_search_pipeline,
        }

    def _resolve_limit(self, limit: int) -> int:
        """Force the optimizer's top_k override, when configured, over any caller-supplied limit."""
        return self._optimizer_config.top_k or limit

    def _record_retrieval_output(self, search_results: list[SearchResult]) -> None:
        """Attach the raw search results as the current retriever span's output.

        The pipeline methods below return a prompt-template string (needed
        for the tool-call result), not the raw `list[SearchResult]` - so the
        real retrieval output (score/content per chunk) is attached
        explicitly here. This is a no-op when Langfuse has no credentials
        configured (`get_client()` returns a disabled client).
        """
        get_client().update_current_span(output=search_results)

    @observe(as_type="retriever")
    async def _hybrid_search_pipeline(
        self,
        query: str,
        keywords: list[str],
        limit: int = 25,
    ) -> str:
        """Pipeline to perform a hybrid search and build a string template."""
        limit = self._resolve_limit(limit)

        query_embedding = await self.embed.generate_embedding(text=query)

        search_results = await self.search.hybrid_search(
            query=query_embedding, keywords=keywords, limit=limit
        )
        self._record_retrieval_output(search_results)

        template = self._build_template(search_results)

        return template

    @observe(as_type="retriever")
    async def _semantic_search_pipeline(self, query: str, limit: int = 25) -> str:
        """Pipeline to perform a semantic search and build a string template."""
        limit = self._resolve_limit(limit)

        query_embedding = await self.embed.generate_embedding(text=query)

        search_results = await self.search.semantic_search(
            query=query_embedding, limit=limit
        )
        self._record_retrieval_output(search_results)

        template = self._build_template(search_results)

        return template

    @observe(as_type="retriever")
    async def _keyword_search_pipeline(
        self,
        keywords: list[str],
        limit: int = 25,
    ) -> str:
        """Pipeline to perform a keyword search and build a string template."""
        limit = self._resolve_limit(limit)

        search_results = await self.search.keyword_search(
            keywords=keywords, limit=limit
        )
        self._record_retrieval_output(search_results)

        template = self._build_template(search_results)

        return template

    def _build_template(self, result: list[SearchResult]) -> str:
        """Use the results of a search to build a string template."""
        return "\n".join(
            [
                "<CONTENT>\n{content}\n</CONTENT>".format(
                    content=search["data"]["content"]
                )
                for search in result
            ]
        )

    async def execute(self, tool_name: str, *args: Any, **kwargs: Any) -> str:
        """Fetch a tool function from the agent's tool map and runs it given the arguments.

        Args:
            tool_name (str): The name of the tool to execute as listed in the agent's tool map.
            *args: Variable-length argument list to pass to the tool function.
            **kwargs: Arbitrary keyword arguments to pass to the tool function.

        Returns:
            The given tool function's return value.

        """
        return await self.tool_map[tool_name](*args, **kwargs)  # type: ignore[operator]

    async def generate(self, messages: Messages, **kwargs: Any) -> AsyncGenerator[str]:
        """Send messages to the LLM to generate a response.

        If the LLM responds with a tool call, execute the tool and
        append the result to the messages list.

        Args:
            messages (Messages): The list of messages to send to the LLM. Each message
                is a dictionary with a "role" key and a "content" key.  The "role" key
                can be "user" or "assistant", and the "content" key is the message
                to send to the LLM.
            **kwargs: Arbitrary keyword arguments to pass to the LLM.

        Returns:
            An asynchronous generator that yields the LLM's response content one token (str) at a time.

        """
        assistant_message: AssistantMessage = {"role": "assistant", "content": ""}

        new_messages: Messages = []
        new_messages.append(assistant_message)

        # Config swap: force the optimizer's max_tokens over anything the
        # caller passed, when configured (same "present -> force it, absent
        # -> unchanged" semantics as the model/prompt/top_k overrides above).
        if self._optimizer_config.max_tokens is not None:
            kwargs["max_tokens"] = self._optimizer_config.max_tokens

        async for chunk in self.chat.generate_stream(
            messages, model=self.model, tools=self.tools, **kwargs
        ):
            if content := chunk["content"]:
                assistant_message["content"] += content
                yield content

            if tools := chunk["tools"]:
                assistant_message["tool_calls"] = tools

                for tool in tools:
                    result = await self.execute(
                        tool_name=tool["function"]["name"],
                        **json.loads(tool["function"]["arguments"]),
                    )

                    new_messages.append(
                        {"role": "tool", "tool_call_id": tool["id"], "content": result}
                    )

        messages.extend(new_messages)

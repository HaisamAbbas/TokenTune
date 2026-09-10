"""`types.chat` provides the chat protocol and the required return types."""

from collections.abc import AsyncGenerator
from typing import Any, Protocol, TypedDict

from .messages import Messages, Tool

__all__ = ["Chat", "OptionalChat", "Stream"]


class StreamPart(TypedDict):
    content: str | None
    tools: list[Tool] | None
    # Non-None only on the terminal usage chunk emitted when the underlying
    # stream requests `stream_options={"include_usage": True}` (Phase 5,
    # needed so callers like the experiment runner see real token counts).
    # Always present (may be None) so existing `chunk["usage"]`-style access
    # never raises KeyError.
    usage: dict[str, int] | None


type Stream = AsyncGenerator[StreamPart]


class Chat(Protocol):
    """Protocol for an chat component."""

    def generate_stream(self, messages: Messages, model: str, **kwargs: Any) -> Stream:
        """Generate a stream of messages from the given messages.

        Args:
            messages: The messages to generate a stream from.
            model: The model to use for generating the stream.
            kwargs: Additional keyword arguments to pass to the model.

        Yields:
            A stream of messages.
        """
        ...


type OptionalChat = Chat | None

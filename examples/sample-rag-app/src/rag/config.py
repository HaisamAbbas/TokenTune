"""`rag.config` configures the application from env variables.

This module configures components based on the attributes of `Settings` and caches them for reuse.
Environment variables are type-checked with pydantic settings to avoid misconfigurations at runtime.

"""

from functools import lru_cache

from pydantic import HttpUrl
from pydantic_settings import BaseSettings

from .components import chat, embed, search

__all__ = ["get_openai_chat", "get_openai_embed", "get_qdrant"]


class Settings(BaseSettings):
    qdrant_collection: str = "my-collection"
    qdrant_url: HttpUrl = HttpUrl("http://localhost:6333")
    qdrant_api_key: str | None = None

    # Chat completions (routed through the LiteLLM proxy, e.g. to GLM via z.ai).
    chat_url: HttpUrl = HttpUrl("http://localhost:4000")
    chat_api_key: str = "None"

    # Embeddings (routed to a dedicated embedding service, e.g. TEI serving BGE-M3).
    # TEI's OpenAI-compatible route is `/v1/embeddings`, so the base URL must include `/v1`.
    openai_embedding_model: str = "bge-m3"
    embed_url: HttpUrl = HttpUrl("http://localhost:8080/v1")
    embed_api_key: str = "None"


settings = Settings()


@lru_cache(1)
def get_qdrant() -> search.QdrantSearch:
    """Create a QdrantSearch instance from type-checked environment variables. Instance is cached on first call."""
    return search.QdrantSearch(
        collection=settings.qdrant_collection,
        url=str(settings.qdrant_url),
        api_key=settings.qdrant_api_key,
    )


@lru_cache(1)
def get_openai_chat() -> chat.OpenAIChat:
    """Create an OpenAIChat instance from type-checked environment variables. Instance is cached on first call."""
    return chat.OpenAIChat(
        base_url=str(settings.chat_url),
        api_key=settings.chat_api_key,
    )


@lru_cache(1)
def get_openai_embed() -> embed.OpenAIEmbed:
    """Create an OpenAIEmbed instance from type-checked environment variables. Instance is cached on first call."""
    return embed.OpenAIEmbed(
        model=settings.openai_embedding_model,
        base_url=str(settings.embed_url),
        api_key=settings.embed_api_key,
    )

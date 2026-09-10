import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.adapters.base import NormalizedRetrievalEvent, NormalizedTelemetryEvent
from app.adapters.langfuse_adapter import LangfuseAdapter
from app.models.project import Project

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _load_fixture(name: str) -> dict:
    with (FIXTURES_DIR / name).open() as f:
        return json.load(f)


def _make_project() -> Project:
    return Project(
        id=uuid.uuid4(),
        name="Test Project",
        slug="test-project",
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test",
    )


def test_fetch_and_normalize_maps_retriever_observation_to_retrieval_event() -> None:
    retriever_observation = _load_fixture("langfuse_retriever_observation.json")
    payload = {"data": [retriever_observation], "meta": {}}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(base_url="https://cloud.langfuse.com", transport=transport)
    adapter = LangfuseAdapter(client=client)
    project = _make_project()

    events = adapter.fetch_and_normalize(
        project,
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 2, tzinfo=UTC),
    )

    assert len(events) == 1
    event = events[0]

    assert isinstance(event, NormalizedRetrievalEvent)
    assert not isinstance(event, NormalizedTelemetryEvent)

    assert event.project_id == project.id
    assert event.trace_id == "trace-42"
    assert event.span_id == "span-retriever-1"
    # top_k comes from the retriever's `limit` kwarg, as captured by
    # Langfuse's @observe(as_type="retriever") on the search pipeline method.
    assert event.top_k == 3
    # chunk_count is len(output); output is the list[SearchResult] the app
    # attaches via langfuse.update_current_span(output=search_results).
    assert event.chunk_count == 3
    # retrieved_tokens is a whitespace-split token estimate over every
    # chunk's `data.content` (34 + 15 + 16 words across the three fixture
    # chunks).
    assert event.retrieved_tokens == 65
    assert event.timestamp == datetime(2026, 1, 1, 0, 0, 30, tzinfo=UTC)
    assert event.metadata == {"tool": "semantic_search"}


def test_fetch_and_normalize_still_maps_untyped_observations_as_llm_calls() -> None:
    """Observations with no "type" (Langfuse's older generation-only shape,
    per the existing fixtures in test_langfuse_adapter.py) must keep being
    treated as LLM calls -- adding retriever mapping must not be a breaking
    change for the existing generation mapping."""
    llm_observation = {
        "core": {"id": "span-1", "traceId": "trace-1"},
        "basic": {"name": "rag-workflow", "startTime": "2026-01-01T00:00:00+00:00"},
        "usage": {"input": 100, "output": 50, "total": 150},
        "model": {"name": "gpt-4o", "provider": "openai"},
    }
    payload = {"data": [llm_observation], "meta": {}}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(base_url="https://cloud.langfuse.com", transport=transport)
    adapter = LangfuseAdapter(client=client)
    project = _make_project()

    events = adapter.fetch_and_normalize(
        project,
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 2, tzinfo=UTC),
    )

    assert len(events) == 1
    assert isinstance(events[0], NormalizedTelemetryEvent)

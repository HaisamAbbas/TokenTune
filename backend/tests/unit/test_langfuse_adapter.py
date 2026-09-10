import uuid
from datetime import UTC, datetime
from decimal import Decimal

import httpx

from app.adapters.langfuse_adapter import LangfuseAdapter
from app.models.project import Project

PAGE_1 = {
    "data": [
        {
            "core": {"id": "span-1", "traceId": "trace-1"},
            "basic": {"name": "rag-workflow", "startTime": "2026-01-01T00:00:00+00:00"},
            "usage": {"input": 100, "output": 50, "total": 150, "totalCost": 0.01},
            "model": {"name": "gpt-4o", "provider": "openai"},
            "metrics": {"latency": 250.5},
            "metadata": {"foo": "bar"},
        }
    ],
    "meta": {"cursor": "cursor-abc"},
}

PAGE_2 = {
    "data": [
        {
            "core": {"id": "span-2", "traceId": "trace-1"},
            "basic": {"name": "rag-workflow", "startTime": "2026-01-01T00:01:00+00:00"},
            "usage": {"input": 20, "output": 10, "total": 30},
            "model": {"name": "gpt-4o-mini", "provider": "openai"},
            "metrics": {"latency": 100.0},
        }
    ],
    "meta": {},
}


def _make_project() -> Project:
    return Project(
        id=uuid.uuid4(),
        name="Test Project",
        slug="test-project",
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test",
    )


def test_fetch_and_normalize_paginates_and_maps_fields() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if "cursor" not in request.url.params:
            return httpx.Response(200, json=PAGE_1)
        assert request.url.params["cursor"] == "cursor-abc"
        return httpx.Response(200, json=PAGE_2)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(base_url="https://cloud.langfuse.com", transport=transport)
    adapter = LangfuseAdapter(client=client)
    project = _make_project()

    events = adapter.fetch_and_normalize(
        project,
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 2, tzinfo=UTC),
    )

    assert len(calls) == 2
    assert len(events) == 2

    first = events[0]
    assert first.trace_id == "trace-1"
    assert first.span_id == "span-1"
    assert first.workflow == "rag-workflow"
    assert first.model == "gpt-4o"
    assert first.provider == "openai"
    assert first.input_tokens == 100
    assert first.output_tokens == 50
    assert first.total_tokens == 150
    assert first.cost == Decimal("0.01")
    assert first.latency_ms == 250.5
    assert first.timestamp == datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    assert first.metadata == {"foo": "bar"}

    second = events[1]
    assert second.span_id == "span-2"
    assert second.cost is None
    assert second.metadata == {}

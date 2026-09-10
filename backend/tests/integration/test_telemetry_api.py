
import httpx
import pytest
from fastapi.testclient import TestClient

import app.services.ingestion as ingestion_module

OBSERVATIONS_PAGE = {
    "data": [
        {
            "core": {"id": "span-1", "traceId": "trace-1"},
            "basic": {"name": "rag-workflow", "startTime": "2026-01-01T00:00:00+00:00"},
            "usage": {"input": 100, "output": 50, "total": 150, "totalCost": 0.01},
            "model": {"name": "gpt-4o", "provider": "openai"},
            "metrics": {"latency": 250.5},
            "metadata": {},
        },
        {
            "core": {"id": "span-2", "traceId": "trace-1"},
            "basic": {"name": "rag-workflow", "startTime": "2026-01-01T00:01:00+00:00"},
            "usage": {"input": 10, "output": 5, "total": 15},
            "model": {"name": "gpt-4o-mini", "provider": "openai"},
            "metrics": {"latency": 90.0},
        },
    ],
    "meta": {},
}


@pytest.fixture()
def mocked_langfuse_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=OBSERVATIONS_PAGE)

    transport = httpx.MockTransport(handler)
    test_client = httpx.Client(base_url="https://cloud.langfuse.com", transport=transport)

    original_langfuse_adapter = ingestion_module.LangfuseAdapter

    def factory(*args: object, **kwargs: object) -> ingestion_module.LangfuseAdapter:
        return original_langfuse_adapter(client=test_client)

    monkeypatch.setattr(ingestion_module, "LangfuseAdapter", factory)


def _create_project(client: TestClient) -> dict:
    response = client.post(
        "/projects",
        json={
            "name": "Telemetry Project",
            "slug": "telemetry-project",
            "langfuse_public_key": "pk-test",
            "langfuse_secret_key": "sk-test",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_import_telemetry_persists_traces_and_llm_calls(
    client: TestClient, mocked_langfuse_adapter: None
) -> None:
    project = _create_project(client)

    response = client.post(
        f"/projects/{project['id']}/telemetry/import",
        json={"from_ts": "2026-01-01T00:00:00Z", "to_ts": "2026-01-02T00:00:00Z"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["traces_created"] == 1
    assert body["llm_calls_created"] == 2
    assert body["retrieval_steps_created"] == 0


def test_import_telemetry_is_idempotent_on_rerun(
    client: TestClient, mocked_langfuse_adapter: None
) -> None:
    project = _create_project(client)
    payload = {"from_ts": "2026-01-01T00:00:00Z", "to_ts": "2026-01-02T00:00:00Z"}

    first = client.post(f"/projects/{project['id']}/telemetry/import", json=payload)
    second = client.post(f"/projects/{project['id']}/telemetry/import", json=payload)

    assert first.json() == {
        "traces_created": 1,
        "llm_calls_created": 2,
        "retrieval_steps_created": 0,
    }
    assert second.json() == {
        "traces_created": 0,
        "llm_calls_created": 0,
        "retrieval_steps_created": 0,
    }


RETRIEVER_OBSERVATIONS_PAGE = {
    "data": [
        {
            "core": {"id": "span-1", "traceId": "trace-1"},
            "basic": {"name": "rag-workflow", "startTime": "2026-01-01T00:00:00+00:00"},
            "usage": {"input": 100, "output": 50, "total": 150, "totalCost": 0.01},
            "model": {"name": "gpt-4o", "provider": "openai"},
        },
        {
            "core": {"id": "span-retriever-1", "traceId": "trace-1", "type": "retriever"},
            "basic": {"name": "_semantic_search_pipeline", "startTime": "2026-01-01T00:00:01+00:00"},
            "io": {
                "input": {"args": [], "kwargs": {"query": "hot planet?", "limit": 3}},
                "output": [
                    {"score": 0.9, "data": {"content": "Venus is hot."}},
                    {"score": 0.5, "data": {"content": "Mercury is small."}},
                ],
            },
        },
    ],
    "meta": {},
}


@pytest.fixture()
def mocked_langfuse_adapter_with_retriever(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=RETRIEVER_OBSERVATIONS_PAGE)

    transport = httpx.MockTransport(handler)
    test_client = httpx.Client(base_url="https://cloud.langfuse.com", transport=transport)

    original_langfuse_adapter = ingestion_module.LangfuseAdapter

    def factory(*args: object, **kwargs: object) -> ingestion_module.LangfuseAdapter:
        return original_langfuse_adapter(client=test_client)

    monkeypatch.setattr(ingestion_module, "LangfuseAdapter", factory)


def test_import_telemetry_persists_retrieval_steps(
    client: TestClient, mocked_langfuse_adapter_with_retriever: None
) -> None:
    project = _create_project(client)

    response = client.post(
        f"/projects/{project['id']}/telemetry/import",
        json={"from_ts": "2026-01-01T00:00:00Z", "to_ts": "2026-01-02T00:00:00Z"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["traces_created"] == 1
    assert body["llm_calls_created"] == 1
    assert body["retrieval_steps_created"] == 1


def test_project_response_never_leaks_langfuse_keys(client: TestClient) -> None:
    project = _create_project(client)
    assert "langfuse_public_key" not in project
    assert "langfuse_secret_key" not in project

    get_response = client.get(f"/projects/{project['id']}")
    body = get_response.json()
    assert "langfuse_public_key" not in body
    assert "langfuse_secret_key" not in body

    list_response = client.get("/projects")
    for item in list_response.json():
        assert "langfuse_public_key" not in item
        assert "langfuse_secret_key" not in item

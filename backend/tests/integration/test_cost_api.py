import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.telemetry import LLMCall, Trace


def _create_project(client: TestClient) -> dict:
    response = client.post("/projects", json={"name": "Cost Project", "slug": "cost-project"})
    assert response.status_code == 201
    return response.json()


def _seed_llm_calls(db_session: Session, project_id: str) -> None:
    project_id = uuid.UUID(project_id)
    trace_1 = Trace(
        project_id=project_id,
        external_trace_id="trace-1",
        workflow="rag-workflow",
        timestamp=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
    )
    trace_2 = Trace(
        project_id=project_id,
        external_trace_id="trace-2",
        workflow="summarization",
        timestamp=datetime(2026, 1, 2, 10, 0, tzinfo=UTC),
    )
    db_session.add_all([trace_1, trace_2])
    db_session.flush()

    db_session.add_all(
        [
            LLMCall(
                trace_id=trace_1.id,
                span_id="span-1",
                model="gpt-4o",
                provider="openai",
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                cost=1.5,
                latency_ms=200.0,
                timestamp=trace_1.timestamp,
            ),
            LLMCall(
                trace_id=trace_1.id,
                span_id="span-2",
                model="gpt-4o-mini",
                provider="openai",
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                cost=0.1,
                latency_ms=100.0,
                timestamp=trace_1.timestamp,
            ),
            LLMCall(
                trace_id=trace_2.id,
                span_id="span-3",
                model="gpt-4o",
                provider="openai",
                input_tokens=20,
                output_tokens=10,
                total_tokens=30,
                cost=0.3,
                latency_ms=300.0,
                timestamp=trace_2.timestamp,
            ),
        ]
    )
    db_session.commit()


def test_cost_flat_summary(client: TestClient, db_session: Session) -> None:
    project = _create_project(client)
    _seed_llm_calls(db_session, project["id"])

    response = client.get(
        f"/projects/{project['id']}/cost",
        params={"from_ts": "2026-01-01T00:00:00Z", "to_ts": "2026-01-03T00:00:00Z"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    row = body[0]
    assert row["request_count"] == 3
    assert float(row["total_cost"]) == 1.9
    assert row["total_input_tokens"] == 130
    assert row["total_output_tokens"] == 65
    assert row["total_tokens"] == 195


def test_cost_group_by_model(client: TestClient, db_session: Session) -> None:
    project = _create_project(client)
    _seed_llm_calls(db_session, project["id"])

    response = client.get(
        f"/projects/{project['id']}/cost",
        params={
            "from_ts": "2026-01-01T00:00:00Z",
            "to_ts": "2026-01-03T00:00:00Z",
            "group_by": "model",
        },
    )
    assert response.status_code == 200
    body = {row["bucket"]: row for row in response.json()}
    assert set(body.keys()) == {"gpt-4o", "gpt-4o-mini"}
    assert body["gpt-4o"]["request_count"] == 2
    assert float(body["gpt-4o"]["total_cost"]) == 1.8
    assert body["gpt-4o-mini"]["request_count"] == 1


def test_cost_group_by_workflow(client: TestClient, db_session: Session) -> None:
    project = _create_project(client)
    _seed_llm_calls(db_session, project["id"])

    response = client.get(
        f"/projects/{project['id']}/cost",
        params={
            "from_ts": "2026-01-01T00:00:00Z",
            "to_ts": "2026-01-03T00:00:00Z",
            "group_by": "workflow",
        },
    )
    assert response.status_code == 200
    body = {row["bucket"]: row for row in response.json()}
    assert set(body.keys()) == {"rag-workflow", "summarization"}
    assert body["rag-workflow"]["request_count"] == 2
    assert body["summarization"]["request_count"] == 1


def test_cost_group_by_day(client: TestClient, db_session: Session) -> None:
    project = _create_project(client)
    _seed_llm_calls(db_session, project["id"])

    response = client.get(
        f"/projects/{project['id']}/cost",
        params={
            "from_ts": "2026-01-01T00:00:00Z",
            "to_ts": "2026-01-03T00:00:00Z",
            "group_by": "day",
        },
    )
    assert response.status_code == 200
    body = {row["bucket"]: row for row in response.json()}
    assert set(body.keys()) == {"2026-01-01", "2026-01-02"}
    assert body["2026-01-01"]["request_count"] == 2
    assert body["2026-01-02"]["request_count"] == 1

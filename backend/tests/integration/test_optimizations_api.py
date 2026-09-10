import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.project import Environment
from app.models.telemetry import LLMCall, RetrievalStep, Trace

FROM_TS = "2026-01-01T00:00:00Z"
TO_TS = "2026-02-01T00:00:00Z"


def _create_project(client: TestClient, slug: str = "opt-project") -> dict:
    response = client.post("/projects", json={"name": "Opt Project", "slug": slug})
    assert response.status_code == 201
    return response.json()


def _seed_excessive_retrieval_traces(
    db_session: Session,
    project_id: str,
    environment_id: uuid.UUID | None = None,
    count: int = 25,
) -> None:
    """Seeds `count` traces whose retrieval context dominates the input
    prompt (well above rule A's 40% threshold), enough to clear
    MIN_SAMPLE_SIZE and trigger the excessive_retrieval_context rule."""
    project_uuid = uuid.UUID(project_id)
    for i in range(count):
        ts = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
        trace = Trace(
            project_id=project_uuid,
            environment_id=environment_id,
            external_trace_id=f"trace-{environment_id}-{i}",
            workflow="rag-workflow",
            timestamp=ts,
        )
        db_session.add(trace)
        db_session.flush()

        db_session.add(
            LLMCall(
                trace_id=trace.id,
                span_id=f"span-{environment_id}-{i}",
                model="gpt-4o",
                provider="openai",
                input_tokens=1000,
                output_tokens=100,
                total_tokens=1100,
                cost=0.01,
                latency_ms=200.0,
                timestamp=ts,
            )
        )
        db_session.add(
            RetrievalStep(
                trace_id=trace.id,
                top_k=20,
                chunk_count=20,
                retrieved_tokens=800,
                timestamp=ts,
            )
        )
    db_session.commit()


def test_analyze_creates_recommendation(client: TestClient, db_session: Session) -> None:
    project = _create_project(client)
    _seed_excessive_retrieval_traces(db_session, project["id"])

    response = client.post(
        f"/projects/{project['id']}/optimizations/analyze",
        json={"from_ts": FROM_TS, "to_ts": TO_TS},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["recommendations_created"] >= 1

    rule_names = {r["rule_name"] for r in body["recommendations"]}
    assert "excessive_retrieval_context" in rule_names

    recommendation = next(
        r for r in body["recommendations"] if r["rule_name"] == "excessive_retrieval_context"
    )
    assert recommendation["project_id"] == project["id"]
    assert recommendation["workflow"] == "rag-workflow"
    assert recommendation["status"] == "pending"
    assert recommendation["proposed_config"]["top_k"] < recommendation["current_config"]["top_k"]
    assert 0.0 <= recommendation["confidence"] <= 1.0


def test_list_optimizations(client: TestClient, db_session: Session) -> None:
    project = _create_project(client)
    _seed_excessive_retrieval_traces(db_session, project["id"])

    analyze_response = client.post(
        f"/projects/{project['id']}/optimizations/analyze",
        json={"from_ts": FROM_TS, "to_ts": TO_TS},
    )
    assert analyze_response.status_code == 200
    created_count = analyze_response.json()["recommendations_created"]
    assert created_count >= 1

    list_response = client.get(f"/projects/{project['id']}/optimizations")
    assert list_response.status_code == 200
    body = list_response.json()
    assert len(body) == created_count
    assert all(r["project_id"] == project["id"] for r in body)


def test_analyze_separates_recommendations_by_environment(
    client: TestClient, db_session: Session
) -> None:
    project = _create_project(client)
    project_uuid = uuid.UUID(project["id"])

    env_hot = Environment(project_id=project_uuid, name="production")
    env_cold = Environment(project_id=project_uuid, name="staging")
    db_session.add_all([env_hot, env_cold])
    db_session.commit()

    # env_hot gets excessive-retrieval traces (should trigger rule A).
    _seed_excessive_retrieval_traces(db_session, project["id"], environment_id=env_hot.id)

    # env_cold gets the same workflow but with lean retrieval (should not
    # trigger rule A).
    for i in range(25):
        ts = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
        trace = Trace(
            project_id=project_uuid,
            environment_id=env_cold.id,
            external_trace_id=f"trace-cold-{i}",
            workflow="rag-workflow",
            timestamp=ts,
        )
        db_session.add(trace)
        db_session.flush()
        db_session.add(
            LLMCall(
                trace_id=trace.id,
                span_id=f"span-cold-{i}",
                model="gpt-4o",
                provider="openai",
                input_tokens=1000,
                output_tokens=100,
                total_tokens=1100,
                cost=0.01,
                latency_ms=200.0,
                timestamp=ts,
            )
        )
        db_session.add(
            RetrievalStep(
                trace_id=trace.id,
                top_k=20,
                chunk_count=5,
                retrieved_tokens=100,
                timestamp=ts,
            )
        )
    db_session.commit()

    response = client.post(
        f"/projects/{project['id']}/optimizations/analyze",
        json={"from_ts": FROM_TS, "to_ts": TO_TS},
    )
    assert response.status_code == 200
    recommendations = response.json()["recommendations"]
    retrieval_recs = [r for r in recommendations if r["rule_name"] == "excessive_retrieval_context"]

    assert any(r["environment_id"] == str(env_hot.id) for r in retrieval_recs)
    assert all(r["environment_id"] != str(env_cold.id) for r in retrieval_recs)

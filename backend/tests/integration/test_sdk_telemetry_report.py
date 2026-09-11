from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.telemetry import LLMCall, Trace


def _create_project(client: TestClient, slug: str = "sdk-report-project") -> dict:
    response = client.post("/projects", json={"name": "SDK Report Project", "slug": slug})
    assert response.status_code == 201
    return response.json()


def test_report_creates_trace_and_llm_call_tagged_sdk_report(
    client: TestClient, db_session: Session
) -> None:
    project = _create_project(client)

    response = client.post(
        "/sdk/telemetry/report",
        json={
            "project_slug": project["slug"],
            "items": [
                {
                    "trace_id": "trace-abc",
                    "model": "gpt-4o-mini",
                    "input_tokens": 120,
                    "output_tokens": 40,
                    "latency_ms": 350.0,
                    "cost": 0.002,
                    "quality_score": 0.87,
                    "workflow": "support-rag",
                    "timestamp": "2026-09-11T00:00:00Z",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["traces_created"] == 1
    assert body["llm_calls_created"] == 1

    trace = db_session.query(Trace).filter(Trace.external_trace_id == "trace-abc").one()
    assert trace.source == "sdk_report"
    assert trace.workflow == "support-rag"

    llm_call = db_session.query(LLMCall).filter(LLMCall.trace_id == trace.id).one()
    assert llm_call.model == "gpt-4o-mini"
    assert llm_call.input_tokens == 120
    assert float(llm_call.cost) == 0.002
    assert llm_call.metadata_ == {"quality_score": 0.87}


def test_report_is_idempotent_for_the_same_trace_id(
    client: TestClient, db_session: Session
) -> None:
    project = _create_project(client, slug="sdk-report-idempotent")
    payload = {
        "project_slug": project["slug"],
        "items": [
            {
                "trace_id": "trace-repeat",
                "model": "gpt-4o-mini",
                "input_tokens": 10,
                "output_tokens": 5,
                "latency_ms": 100.0,
                "timestamp": "2026-09-11T00:00:00Z",
            }
        ],
    }

    first = client.post("/sdk/telemetry/report", json=payload)
    second = client.post("/sdk/telemetry/report", json=payload)

    assert first.json() == {"traces_created": 1, "llm_calls_created": 1}
    assert second.json() == {"traces_created": 0, "llm_calls_created": 0}

    assert db_session.query(Trace).filter(Trace.external_trace_id == "trace-repeat").count() == 1


def test_report_defaults_langfuse_imported_traces_to_that_source(
    client: TestClient, db_session: Session
) -> None:
    """Backward compatibility: a trace created via the existing Langfuse
    import path (not exercised here directly, just the model default) must
    default to "langfuse_import", not "sdk_report". SQLAlchemy's Python-side
    `default=` applies at flush time, not at construction, so the object
    must actually be flushed before checking."""
    from datetime import UTC, datetime

    from app.models.project import Project

    project = Project(name="Backcompat Project", slug="backcompat-project")
    db_session.add(project)
    db_session.flush()

    trace = Trace(
        project_id=project.id,
        external_trace_id="whatever",
        timestamp=datetime.now(UTC),
    )
    db_session.add(trace)
    db_session.flush()

    assert trace.source == "langfuse_import"


def test_report_unknown_project_slug_returns_404(client: TestClient, db_session: Session) -> None:
    response = client.post(
        "/sdk/telemetry/report",
        json={"project_slug": "does-not-exist", "items": []},
    )
    assert response.status_code == 404

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.optimization import OptimizationRecommendation
from app.models.project import Project
from app.models.telemetry import LLMCall, Trace
from app.services.metrics import get_project_metrics

FROM_TS = datetime(2026, 1, 1, tzinfo=UTC)
TO_TS = datetime(2026, 2, 1, tzinfo=UTC)


def _make_recommendation(project_id, status: str, savings_low, savings_high) -> OptimizationRecommendation:
    return OptimizationRecommendation(
        project_id=project_id,
        rule_name="excessive_retrieval_context",
        reason="stub",
        current_config={},
        proposed_config={},
        estimated_cost_impact="stub",
        required_experiment={},
        confidence=0.9,
        confidence_bucket="high",
        estimated_savings_low=savings_low,
        estimated_savings_high=savings_high,
        status=status,
    )


def test_metrics_sums_only_open_recommendations(db_session: Session) -> None:
    project = Project(name="Metrics Project", slug="metrics-project")
    db_session.add(project)
    db_session.commit()

    ts = datetime(2026, 1, 15, tzinfo=UTC)
    trace = Trace(project_id=project.id, external_trace_id="t1", timestamp=ts)
    db_session.add(trace)
    db_session.flush()
    db_session.add(
        LLMCall(
            trace_id=trace.id,
            model="gpt-4o",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cost=1.5,
            timestamp=ts,
        )
    )

    db_session.add(_make_recommendation(project.id, "pending", 10.0, 20.0))
    db_session.add(_make_recommendation(project.id, "validated", 5.0, 8.0))
    # Terminal states must be excluded from the open-savings total.
    db_session.add(_make_recommendation(project.id, "adopted", 100.0, 200.0))
    db_session.add(_make_recommendation(project.id, "rejected", 100.0, 200.0))
    db_session.commit()

    metrics = get_project_metrics(db_session, project.id, FROM_TS, TO_TS)

    assert metrics.total_spend == 1.5
    assert metrics.total_potential_savings_low == 15.0
    assert metrics.total_potential_savings_high == 28.0
    assert metrics.open_opportunity_count == 2


def test_metrics_are_zero_with_no_data(db_session: Session) -> None:
    project = Project(name="Empty Project", slug="empty-project")
    db_session.add(project)
    db_session.commit()

    metrics = get_project_metrics(db_session, project.id, FROM_TS, TO_TS)

    assert metrics.total_spend == 0.0
    assert metrics.total_potential_savings_low == 0.0
    assert metrics.total_potential_savings_high == 0.0
    assert metrics.open_opportunity_count == 0

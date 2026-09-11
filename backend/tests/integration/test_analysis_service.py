from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.telemetry import LLMCall, RetrievalStep, Trace
from app.services.analysis import SIMPLE_COMPLEXITY_TOKEN_THRESHOLD, _build_workflow_stats
from app.services.rules.base import MIN_SAMPLE_SIZE

FROM_TS = datetime(2026, 1, 1, tzinfo=UTC)
TO_TS = datetime(2026, 2, 1, tzinfo=UTC)


def test_retrieval_averages_are_summed_per_trace_then_averaged(db_session: Session) -> None:
    """A trace with multiple retrieval steps (e.g. multi-hop retrieval) must
    have its retrieval tokens/top_k summed per-trace before being averaged
    across traces - averaging directly over every RetrievalStep row would
    understate multi-hop workflows by diluting per-trace totals across more
    rows."""
    project = Project(name="Analysis Project", slug="analysis-project")
    db_session.add(project)
    db_session.commit()

    ts = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)

    # Trace A: two retrieval steps (multi-hop) - per-trace sum is 600
    # tokens / top_k 20.
    trace_a = Trace(
        project_id=project.id,
        external_trace_id="trace-a",
        workflow="rag-workflow",
        timestamp=ts,
    )
    db_session.add(trace_a)
    db_session.flush()
    db_session.add(
        LLMCall(
            trace_id=trace_a.id,
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=100,
            total_tokens=1100,
            cost=0.01,
            timestamp=ts,
        )
    )
    db_session.add_all(
        [
            RetrievalStep(trace_id=trace_a.id, top_k=10, chunk_count=10, retrieved_tokens=300, timestamp=ts),
            RetrievalStep(trace_id=trace_a.id, top_k=10, chunk_count=10, retrieved_tokens=300, timestamp=ts),
        ]
    )

    # Trace B: single retrieval step - per-trace sum is 100 tokens / top_k 5.
    trace_b = Trace(
        project_id=project.id,
        external_trace_id="trace-b",
        workflow="rag-workflow",
        timestamp=ts,
    )
    db_session.add(trace_b)
    db_session.flush()
    db_session.add(
        LLMCall(
            trace_id=trace_b.id,
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=100,
            total_tokens=1100,
            cost=0.01,
            timestamp=ts,
        )
    )
    db_session.add(
        RetrievalStep(trace_id=trace_b.id, top_k=5, chunk_count=5, retrieved_tokens=100, timestamp=ts)
    )
    db_session.commit()

    stats = _build_workflow_stats(
        db_session, project.id, "rag-workflow", None, FROM_TS, TO_TS
    )

    assert stats is not None
    # Per-trace sums are 600 and 100 -> average 350, NOT the flat-pool
    # average of (300+300+100)/3 = 233.33 across all three rows.
    assert stats.avg_retrieval_tokens == 350.0
    # Per-trace top_k sums are 20 and 5 -> average 12.5.
    assert stats.avg_top_k == 12.5


def _add_trace_with_call(db_session: Session, project: Project, ts: datetime, input_tokens: int) -> None:
    trace = Trace(
        project_id=project.id,
        external_trace_id=f"trace-{uuid_hex()}",
        workflow="rag-workflow",
        timestamp=ts,
    )
    db_session.add(trace)
    db_session.flush()
    db_session.add(
        LLMCall(
            trace_id=trace.id,
            model="gpt-4o",
            input_tokens=input_tokens,
            output_tokens=100,
            total_tokens=input_tokens + 100,
            cost=0.01,
            timestamp=ts,
        )
    )


def uuid_hex() -> str:
    import uuid

    return uuid.uuid4().hex


def test_segments_are_computed_when_both_sides_meet_min_sample_size(db_session: Session) -> None:
    project = Project(name="Segment Project", slug="segment-project")
    db_session.add(project)
    db_session.commit()

    ts = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    for _ in range(MIN_SAMPLE_SIZE):
        _add_trace_with_call(db_session, project, ts, int(SIMPLE_COMPLEXITY_TOKEN_THRESHOLD - 100))
    for _ in range(MIN_SAMPLE_SIZE):
        _add_trace_with_call(db_session, project, ts, int(SIMPLE_COMPLEXITY_TOKEN_THRESHOLD + 1000))
    db_session.commit()

    stats = _build_workflow_stats(db_session, project.id, "rag-workflow", None, FROM_TS, TO_TS)

    assert stats is not None
    assert stats.segments is not None
    assert stats.segments["simple"].trace_count == MIN_SAMPLE_SIZE
    assert stats.segments["complex"].trace_count == MIN_SAMPLE_SIZE


def test_segments_are_none_when_one_side_below_min_sample_size(db_session: Session) -> None:
    project = Project(name="Unbalanced Project", slug="unbalanced-project")
    db_session.add(project)
    db_session.commit()

    ts = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    for _ in range(MIN_SAMPLE_SIZE):
        _add_trace_with_call(db_session, project, ts, int(SIMPLE_COMPLEXITY_TOKEN_THRESHOLD - 100))
    for _ in range(3):
        _add_trace_with_call(db_session, project, ts, int(SIMPLE_COMPLEXITY_TOKEN_THRESHOLD + 1000))
    db_session.commit()

    stats = _build_workflow_stats(db_session, project.id, "rag-workflow", None, FROM_TS, TO_TS)

    assert stats is not None
    assert stats.segments is None

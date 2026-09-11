import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.optimization import OptimizationRecommendation
from app.models.project import Project
from app.models.telemetry import LLMCall, RetrievalStep, Trace
from app.services.rules import MIN_SAMPLE_SIZE, RuleEngine, WorkflowStats
from app.services.rules.base import percentile

# A recommendation is treated as a duplicate of a prior run - and skipped -
# if a "pending" recommendation with the same
# (project_id, workflow, environment_id, rule_name) was already created
# within this window. This avoids re-analyzing the same window repeatedly
# (e.g. re-running /analyze with an unchanged or overlapping time range) from
# flooding the table with identical rows, while still allowing a fresh
# recommendation once enough time has passed for the underlying stats to have
# meaningfully changed.
DUPLICATE_WINDOW = timedelta(hours=1)

# A trace whose total input tokens fall below this is treated as
# "low-complexity" for Rule E's segmented-routing detection - a deliberately
# crude proxy, not a real complexity classifier (see V2 design decisions).
SIMPLE_COMPLEXITY_TOKEN_THRESHOLD = 500.0

_rule_engine = RuleEngine()


def _per_trace_input_tokens(db: Session, trace_filter: list) -> dict[uuid.UUID, float]:
    rows = (
        db.query(LLMCall.trace_id, func.sum(LLMCall.input_tokens).label("total"))
        .join(Trace, LLMCall.trace_id == Trace.id)
        .filter(*trace_filter)
        .group_by(LLMCall.trace_id)
        .all()
    )
    return {row.trace_id: float(row.total or 0) for row in rows}


def _build_stats_for_filter(
    db: Session,
    project_id: uuid.UUID,
    workflow: str | None,
    environment_id: uuid.UUID | None,
    trace_filter: list,
    window_days: float,
) -> WorkflowStats | None:
    """Compute WorkflowStats for an arbitrary trace_filter - either the whole
    workflow/environment group, or a further-restricted subset of it (e.g. a
    complexity segment). Shared by _build_workflow_stats and
    _build_segment_stats below."""
    trace_count = db.query(func.count(Trace.id)).filter(*trace_filter).scalar() or 0
    if trace_count == 0:
        return None

    call_row = (
        db.query(
            func.count(LLMCall.id).label("call_count"),
            func.avg(LLMCall.input_tokens).label("avg_input_tokens"),
            func.avg(LLMCall.output_tokens).label("avg_output_tokens"),
            func.sum(LLMCall.cost).label("total_cost"),
        )
        .join(Trace, LLMCall.trace_id == Trace.id)
        .filter(*trace_filter)
        .one()
    )
    call_count = call_row.call_count or 0
    avg_input_tokens = float(call_row.avg_input_tokens or 0)
    avg_output_tokens = float(call_row.avg_output_tokens or 0)
    total_cost = float(call_row.total_cost or 0)

    model_rows = (
        db.query(LLMCall.model, func.count(LLMCall.id))
        .join(Trace, LLMCall.trace_id == Trace.id)
        .filter(*trace_filter)
        .group_by(LLMCall.model)
        .all()
    )
    model_usage = {model: count for model, count in model_rows}

    # A trace can have multiple retrieval steps (e.g. multi-hop retrieval).
    # Averaging directly across RetrievalStep rows would understate such
    # workflows by diluting their per-trace totals across more rows, so sum
    # retrieval tokens/top_k per trace first, then average those per-trace
    # totals across traces.
    per_trace_retrieval = (
        db.query(
            RetrievalStep.trace_id.label("trace_id"),
            func.sum(RetrievalStep.retrieved_tokens).label("trace_retrieved_tokens"),
            func.sum(RetrievalStep.top_k).label("trace_top_k"),
        )
        .join(Trace, RetrievalStep.trace_id == Trace.id)
        .filter(*trace_filter)
        .group_by(RetrievalStep.trace_id)
        .subquery()
    )
    retrieval_row = db.query(
        func.avg(per_trace_retrieval.c.trace_retrieved_tokens).label("avg_retrieved_tokens"),
        func.avg(per_trace_retrieval.c.trace_top_k).label("avg_top_k"),
    ).one()
    avg_retrieval_tokens = (
        float(retrieval_row.avg_retrieved_tokens)
        if retrieval_row.avg_retrieved_tokens is not None
        else None
    )
    avg_top_k = float(retrieval_row.avg_top_k) if retrieval_row.avg_top_k is not None else None

    per_trace_tokens = sorted(_per_trace_input_tokens(db, trace_filter).values())
    p95_input_tokens = percentile(per_trace_tokens, 0.95) if per_trace_tokens else None

    return WorkflowStats(
        sample_project_id=project_id,
        workflow=workflow,
        environment_id=environment_id,
        trace_count=trace_count,
        avg_input_tokens=avg_input_tokens,
        avg_output_tokens=avg_output_tokens,
        avg_retrieval_tokens=avg_retrieval_tokens,
        avg_top_k=avg_top_k,
        avg_cost_per_trace=total_cost / trace_count,
        model_usage=model_usage,
        avg_calls_per_trace=call_count / trace_count,
        p95_input_tokens=p95_input_tokens,
        window_days=window_days,
    )


def _build_workflow_stats(
    db: Session,
    project_id: uuid.UUID,
    workflow: str | None,
    environment_id: uuid.UUID | None,
    from_ts: datetime,
    to_ts: datetime,
) -> WorkflowStats | None:
    trace_filter = [
        Trace.project_id == project_id,
        Trace.timestamp >= from_ts,
        Trace.timestamp <= to_ts,
        Trace.workflow == workflow,
        Trace.environment_id == environment_id,
    ]
    window_days = max((to_ts - from_ts).total_seconds() / 86400, 1 / 24)

    stats = _build_stats_for_filter(
        db, project_id, workflow, environment_id, trace_filter, window_days
    )
    if stats is None:
        return None

    stats.segments = _build_segment_stats(
        db, project_id, workflow, environment_id, trace_filter, window_days
    )
    return stats


def _build_segment_stats(
    db: Session,
    project_id: uuid.UUID,
    workflow: str | None,
    environment_id: uuid.UUID | None,
    trace_filter: list,
    window_days: float,
) -> dict[str, WorkflowStats] | None:
    """Split the group's traces into "simple" (below
    SIMPLE_COMPLEXITY_TOKEN_THRESHOLD total input tokens) and "complex"
    segments, and compute WorkflowStats for each - used only by Rule E.
    Returns None when either segment doesn't meet MIN_SAMPLE_SIZE, since a
    segmented recommendation needs enough traces on both sides to be
    trustworthy."""
    per_trace_tokens = _per_trace_input_tokens(db, trace_filter)
    simple_ids = [
        tid for tid, total in per_trace_tokens.items() if total < SIMPLE_COMPLEXITY_TOKEN_THRESHOLD
    ]
    complex_ids = [
        tid
        for tid, total in per_trace_tokens.items()
        if total >= SIMPLE_COMPLEXITY_TOKEN_THRESHOLD
    ]
    if len(simple_ids) < MIN_SAMPLE_SIZE or len(complex_ids) < MIN_SAMPLE_SIZE:
        return None

    simple_stats = _build_stats_for_filter(
        db, project_id, workflow, environment_id, [*trace_filter, Trace.id.in_(simple_ids)], window_days
    )
    complex_stats = _build_stats_for_filter(
        db, project_id, workflow, environment_id, [*trace_filter, Trace.id.in_(complex_ids)], window_days
    )
    if simple_stats is None or complex_stats is None:
        return None
    return {"simple": simple_stats, "complex": complex_stats}


def _is_duplicate(
    db: Session,
    project_id: uuid.UUID,
    workflow: str | None,
    environment_id: uuid.UUID | None,
    rule_name: str,
) -> bool:
    cutoff = datetime.now(UTC) - DUPLICATE_WINDOW
    existing = (
        db.query(OptimizationRecommendation)
        .filter(
            OptimizationRecommendation.project_id == project_id,
            OptimizationRecommendation.workflow == workflow,
            OptimizationRecommendation.environment_id == environment_id,
            OptimizationRecommendation.rule_name == rule_name,
            OptimizationRecommendation.status == "pending",
            OptimizationRecommendation.created_at >= cutoff,
        )
        .first()
    )
    return existing is not None


def run_analysis(
    project: Project,
    from_ts: datetime,
    to_ts: datetime,
    db: Session,
) -> list[OptimizationRecommendation]:
    groups = (
        db.query(Trace.workflow, Trace.environment_id)
        .filter(
            Trace.project_id == project.id,
            Trace.timestamp >= from_ts,
            Trace.timestamp <= to_ts,
        )
        .distinct()
        .all()
    )

    created: list[OptimizationRecommendation] = []
    for workflow, environment_id in groups:
        stats = _build_workflow_stats(db, project.id, workflow, environment_id, from_ts, to_ts)
        if stats is None:
            continue

        for recommendation in _rule_engine.run(stats):
            if _is_duplicate(db, project.id, workflow, environment_id, recommendation.rule_name):
                continue
            row = OptimizationRecommendation(
                project_id=recommendation.project_id,
                workflow=recommendation.workflow,
                environment_id=recommendation.environment_id,
                rule_name=recommendation.rule_name,
                reason=recommendation.reason,
                current_config=recommendation.current_config,
                proposed_config=recommendation.proposed_config,
                estimated_cost_impact=recommendation.estimated_cost_impact,
                required_experiment=recommendation.required_experiment,
                confidence=recommendation.confidence,
                confidence_bucket=recommendation.confidence_bucket,
                evidence=recommendation.evidence,
                estimated_savings_low=recommendation.estimated_savings_low,
                estimated_savings_high=recommendation.estimated_savings_high,
                status=recommendation.status,
            )
            db.add(row)
            created.append(row)

    # No db.refresh() here: id and created_at are populated client-side by
    # Python defaults (uuid.uuid4 / datetime.now(UTC)) at flush time, not by
    # any server_default, so the in-memory rows are already fully populated
    # after commit.
    db.commit()
    return created

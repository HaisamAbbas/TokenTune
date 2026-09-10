import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.optimization import OptimizationRecommendation
from app.models.project import Project
from app.models.telemetry import LLMCall, RetrievalStep, Trace
from app.services.rules import RuleEngine, WorkflowStats

# A recommendation is treated as a duplicate of a prior run - and skipped -
# if a "pending" recommendation with the same
# (project_id, workflow, environment_id, rule_name) was already created
# within this window. This avoids re-analyzing the same window repeatedly
# (e.g. re-running /analyze with an unchanged or overlapping time range) from
# flooding the table with identical rows, while still allowing a fresh
# recommendation once enough time has passed for the underlying stats to have
# meaningfully changed.
DUPLICATE_WINDOW = timedelta(hours=1)

_rule_engine = RuleEngine()


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
    )


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

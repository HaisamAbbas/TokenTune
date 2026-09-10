from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.adapters.base import NormalizedRetrievalEvent, NormalizedTelemetryEvent, TelemetryAdapter
from app.adapters.langfuse_adapter import LangfuseAdapter
from app.models.project import Project
from app.models.telemetry import LLMCall, RetrievalStep, Trace
from app.services.pricing import estimate_cost


@dataclass
class IngestionResult:
    traces_created: int
    llm_calls_created: int
    retrieval_steps_created: int = 0


def import_telemetry(
    project: Project,
    from_ts: datetime,
    to_ts: datetime,
    db: Session,
    adapter: TelemetryAdapter | None = None,
) -> IngestionResult:
    """Fetch normalized telemetry events for a project and upsert them as traces/llm_calls."""
    adapter = adapter or LangfuseAdapter()
    events = adapter.fetch_and_normalize(project, from_ts, to_ts)

    traces_created = 0
    llm_calls_created = 0
    retrieval_steps_created = 0
    trace_cache: dict[str, Trace] = {}

    for event in events:
        workflow = event.workflow if isinstance(event, NormalizedTelemetryEvent) else None

        trace = trace_cache.get(event.trace_id)
        if trace is None:
            trace = (
                db.query(Trace)
                .filter(
                    Trace.project_id == project.id,
                    Trace.external_trace_id == event.trace_id,
                )
                .first()
            )
            if trace is None:
                trace = Trace(
                    project_id=project.id,
                    external_trace_id=event.trace_id,
                    workflow=workflow,
                    timestamp=event.timestamp,
                )
                db.add(trace)
                db.flush()
                traces_created += 1
            trace_cache[event.trace_id] = trace

        if isinstance(event, NormalizedRetrievalEvent):
            retrieval_step = _upsert_retrieval_step(db, trace, event)
            if retrieval_step is not None:
                retrieval_steps_created += 1
            continue

        if event.cost is None:
            event = event.model_copy(
                update={
                    "cost": estimate_cost(event.model, event.input_tokens, event.output_tokens)
                }
            )

        llm_call = _upsert_llm_call(db, trace, event)
        if llm_call is not None:
            llm_calls_created += 1

    db.commit()
    return IngestionResult(
        traces_created=traces_created,
        llm_calls_created=llm_calls_created,
        retrieval_steps_created=retrieval_steps_created,
    )


def _upsert_llm_call(db: Session, trace: Trace, event: NormalizedTelemetryEvent) -> LLMCall | None:
    existing = (
        db.query(LLMCall)
        .filter(LLMCall.trace_id == trace.id, LLMCall.span_id == event.span_id)
        .first()
    )
    if existing is not None:
        return None

    llm_call = LLMCall(
        trace_id=trace.id,
        span_id=event.span_id,
        model=event.model,
        provider=event.provider,
        input_tokens=event.input_tokens,
        output_tokens=event.output_tokens,
        total_tokens=event.total_tokens,
        cost=event.cost,
        latency_ms=event.latency_ms,
        timestamp=event.timestamp,
        metadata_=event.metadata,
    )
    db.add(llm_call)
    db.flush()
    return llm_call


def _upsert_retrieval_step(
    db: Session, trace: Trace, event: NormalizedRetrievalEvent
) -> RetrievalStep | None:
    existing = (
        db.query(RetrievalStep)
        .filter(RetrievalStep.trace_id == trace.id, RetrievalStep.span_id == event.span_id)
        .first()
    )
    if existing is not None:
        return None

    retrieval_step = RetrievalStep(
        trace_id=trace.id,
        span_id=event.span_id,
        top_k=event.top_k,
        chunk_count=event.chunk_count,
        retrieved_tokens=event.retrieved_tokens,
        timestamp=event.timestamp,
        metadata_=event.metadata,
    )
    db.add(retrieval_step)
    db.flush()
    return retrieval_step

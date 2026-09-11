from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.adapters.base import NormalizedRetrievalEvent, NormalizedTelemetryEvent, TelemetryAdapter
from app.adapters.langfuse_adapter import LangfuseAdapter
from app.models.project import Project
from app.models.telemetry import LLMCall, RetrievalStep, Trace
from app.schemas.telemetry import TelemetryReportItem
from app.services.pricing import estimate_cost


@dataclass
class IngestionResult:
    traces_created: int
    llm_calls_created: int
    retrieval_steps_created: int = 0


def report_telemetry(
    project: Project, items: list[TelemetryReportItem], db: Session
) -> IngestionResult:
    """Ingest SDK-reported calls (TokenTune SDK's `client.report(...)`) into
    the same Trace/LLMCall tables Langfuse import populates, tagged
    `source="sdk_report"`. One item = one Trace with exactly one LLMCall -
    the SDK reports per-call, not per-trace, so each reported item gets its
    own trace keyed by the SDK's `trace_id` (idempotent: re-reporting the
    same trace_id updates nothing new, matching import_telemetry's
    upsert-by-external-id behavior)."""
    traces_created = 0
    llm_calls_created = 0

    for item in items:
        trace = (
            db.query(Trace)
            .filter(Trace.project_id == project.id, Trace.external_trace_id == item.trace_id)
            .first()
        )
        if trace is None:
            trace = Trace(
                project_id=project.id,
                external_trace_id=item.trace_id,
                workflow=item.workflow,
                timestamp=item.timestamp,
                source="sdk_report",
            )
            db.add(trace)
            db.flush()
            traces_created += 1

        existing_call = (
            db.query(LLMCall)
            .filter(LLMCall.trace_id == trace.id, LLMCall.span_id == item.trace_id)
            .first()
        )
        if existing_call is not None:
            continue

        cost = item.cost
        if cost is None:
            cost = estimate_cost(item.model, item.input_tokens, item.output_tokens)

        db.add(
            LLMCall(
                trace_id=trace.id,
                span_id=item.trace_id,
                model=item.model,
                input_tokens=item.input_tokens,
                output_tokens=item.output_tokens,
                total_tokens=item.input_tokens + item.output_tokens,
                cost=cost,
                latency_ms=item.latency_ms,
                timestamp=item.timestamp,
                metadata_={"quality_score": item.quality_score}
                if item.quality_score is not None
                else None,
            )
        )
        llm_calls_created += 1

    db.commit()
    return IngestionResult(traces_created=traces_created, llm_calls_created=llm_calls_created)


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

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.telemetry import LLMCall, Trace
from app.schemas.telemetry import CostBucket, GroupBy


def aggregate_cost(
    db: Session,
    project_id: uuid.UUID,
    from_ts: datetime,
    to_ts: datetime,
    group_by: GroupBy | None = None,
) -> list[CostBucket]:
    bucket_col: Any
    if group_by == "day":
        # func.date() truncates a timestamp to its calendar day on both
        # SQLite and PostgreSQL, unlike date_trunc() which is Postgres-only.
        bucket_col = func.date(Trace.timestamp)
    elif group_by == "model":
        bucket_col = LLMCall.model
    elif group_by == "workflow":
        bucket_col = Trace.workflow
    else:
        bucket_col = None

    columns: list[Any] = [
        func.sum(LLMCall.cost).label("total_cost"),
        func.sum(LLMCall.input_tokens).label("total_input_tokens"),
        func.sum(LLMCall.output_tokens).label("total_output_tokens"),
        func.sum(LLMCall.total_tokens).label("total_tokens"),
        func.avg(LLMCall.latency_ms).label("avg_latency_ms"),
        func.count().label("request_count"),
    ]
    if bucket_col is not None:
        columns.insert(0, bucket_col.label("bucket"))

    query = (
        db.query(*columns)
        .join(Trace, LLMCall.trace_id == Trace.id)
        .filter(
            Trace.project_id == project_id,
            Trace.timestamp >= from_ts,
            Trace.timestamp <= to_ts,
        )
    )
    if bucket_col is not None:
        query = query.group_by(bucket_col)

    rows = query.all()

    buckets = []
    for row in rows:
        if bucket_col is not None:
            bucket_value = row.bucket
            bucket_key = str(bucket_value) if bucket_value is not None else None
        else:
            bucket_key = None
        buckets.append(
            CostBucket(
                bucket=bucket_key,
                total_cost=row.total_cost,
                total_input_tokens=row.total_input_tokens or 0,
                total_output_tokens=row.total_output_tokens or 0,
                total_tokens=row.total_tokens or 0,
                avg_latency_ms=row.avg_latency_ms,
                request_count=row.request_count,
            )
        )
    return buckets

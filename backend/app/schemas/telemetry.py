import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


class TelemetryImportRequest(BaseModel):
    from_ts: datetime
    to_ts: datetime

    @field_validator("from_ts", "to_ts")
    @classmethod
    def _coerce_naive_to_utc(cls, value: datetime) -> datetime:
        # Trace.timestamp is stored tz-aware; callers who forget to add a
        # timezone almost always mean UTC, so coerce rather than reject -
        # least surprising for API callers.
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class TelemetryImportResult(BaseModel):
    traces_created: int
    llm_calls_created: int
    retrieval_steps_created: int


class CostBucket(BaseModel):
    bucket: str | None
    total_cost: Decimal | None
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    avg_latency_ms: float | None
    request_count: int


GroupBy = Literal["day", "model", "workflow"]


class TraceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    environment_id: uuid.UUID | None
    external_trace_id: str
    workflow: str | None
    timestamp: datetime
    metadata_: dict | None


class RetrievalStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    trace_id: uuid.UUID
    top_k: int | None
    chunk_count: int | None
    retrieved_tokens: int | None
    timestamp: datetime
    metadata_: dict | None


class LLMCallRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    trace_id: uuid.UUID
    span_id: str | None
    model: str
    provider: str | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: float | None
    latency_ms: float | None
    timestamp: datetime
    metadata_: dict | None

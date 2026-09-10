import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TraceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    environment_id: uuid.UUID | None
    external_trace_id: str
    workflow: str | None
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

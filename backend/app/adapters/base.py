import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.project import Project


class NormalizedTelemetryEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: uuid.UUID
    trace_id: str
    span_id: str | None
    workflow: str | None = None
    model: str
    provider: str | None = None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: Decimal | None = None
    latency_ms: float | None = None
    timestamp: datetime
    metadata: dict = {}


class TelemetryAdapter(ABC):
    @abstractmethod
    def fetch_and_normalize(
        self, project: Project, from_ts: datetime, to_ts: datetime
    ) -> list[NormalizedTelemetryEvent]:
        raise NotImplementedError

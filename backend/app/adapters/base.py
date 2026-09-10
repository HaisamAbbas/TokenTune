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


class NormalizedRetrievalEvent(BaseModel):
    """A Retrieval Step observation, normalized from a source's wire format.

    Parallel to `NormalizedTelemetryEvent` rather than a subclass of it: a
    retrieval observation has no token/cost/model fields (it isn't a
    generation), so folding it into one class would mean most fields are
    meaningless for one of the two cases. `fetch_and_normalize` returns a
    mixed list of both shapes; callers (e.g. the ingestion service) switch on
    type to decide whether to persist an `LLMCall` or a `RetrievalStep`.
    """

    model_config = ConfigDict(frozen=True)

    project_id: uuid.UUID
    trace_id: str
    span_id: str | None
    top_k: int | None = None
    chunk_count: int | None = None
    retrieved_tokens: int | None = None
    timestamp: datetime
    metadata: dict = {}


class TelemetryAdapter(ABC):
    @abstractmethod
    def fetch_and_normalize(
        self, project: Project, from_ts: datetime, to_ts: datetime
    ) -> list[NormalizedTelemetryEvent | NormalizedRetrievalEvent]:
        raise NotImplementedError

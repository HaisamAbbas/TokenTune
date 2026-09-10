import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

ExperimentStatus = Literal["pending", "running", "completed", "failed"]
Variant = Literal["baseline", "experiment"]


class ExperimentCreate(BaseModel):
    recommendation_id: uuid.UUID | None = None
    name: str
    baseline_config: dict[str, Any]
    experiment_config: dict[str, Any]
    evaluation_dataset_id: uuid.UUID


class ExperimentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    recommendation_id: uuid.UUID | None
    name: str
    baseline_config: dict[str, Any]
    experiment_config: dict[str, Any]
    evaluation_dataset_id: uuid.UUID
    status: ExperimentStatus
    error: str | None
    created_at: datetime


class ExperimentRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    experiment_id: uuid.UUID
    variant: Variant
    metrics: dict[str, Any]
    started_at: datetime
    completed_at: datetime | None


class ExperimentComparisonResult(BaseModel):
    """The agreed API shape for a completed run: both variants' raw runs
    plus the derived comparison the platform's success criteria are stated
    in terms of (cost reduction %, quality difference, latency difference,
    token reduction %)."""

    experiment: ExperimentRead
    baseline_run: ExperimentRunRead
    experiment_run: ExperimentRunRead
    cost_reduction_pct: float
    quality_difference: float
    latency_difference_ms: float
    token_reduction_pct: float
    failed_questions: list[str]

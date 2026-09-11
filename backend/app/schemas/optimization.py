import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator

RuleName = Literal[
    "excessive_retrieval_context",
    "model_cost_optimization",
    "prompt_optimization",
    "unnecessary_generation_calls",
    "segmented_model_routing",
]


class OptimizationRecommendationCreate(BaseModel):
    project_id: uuid.UUID
    workflow: str | None = None
    environment_id: uuid.UUID | None = None
    rule_name: RuleName
    reason: str
    current_config: dict[str, Any]
    proposed_config: dict[str, Any]
    estimated_cost_impact: str
    required_experiment: dict[str, Any]
    confidence: float
    confidence_bucket: str | None = None
    evidence: dict[str, Any] | None = None
    estimated_savings_low: float | None = None
    estimated_savings_high: float | None = None
    status: str = "pending"


class OptimizationRecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    workflow: str | None
    environment_id: uuid.UUID | None
    rule_name: str
    reason: str
    current_config: dict[str, Any]
    proposed_config: dict[str, Any]
    estimated_cost_impact: str
    required_experiment: dict[str, Any]
    experiment_id: uuid.UUID | None
    confidence: float
    confidence_bucket: str | None
    evidence: dict[str, Any] | None
    estimated_savings_low: float | None
    estimated_savings_high: float | None
    status: str
    created_at: datetime


class OptimizationRecommendationStatusUpdate(BaseModel):
    """Body for PATCH /projects/{id}/optimizations/{recommendation_id}.

    Business rule (enforced in the endpoint, not here): `adopted` requires a
    linked Experiment that has completed; `rejected` is allowed at any time.
    This only ever updates the recommendation's `status` field - it never
    mutates any production configuration.
    """

    status: Literal["adopted", "rejected"]


class AnalyzeRequest(BaseModel):
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


class AnalyzeResult(BaseModel):
    recommendations_created: int
    recommendations: list[OptimizationRecommendationRead]

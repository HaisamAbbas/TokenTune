import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

RuleName = Literal[
    "excessive_retrieval_context",
    "model_cost_optimization",
    "prompt_optimization",
    "unnecessary_generation_calls",
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
    confidence: float
    status: str
    created_at: datetime


class AnalyzeRequest(BaseModel):
    from_ts: datetime
    to_ts: datetime


class AnalyzeResult(BaseModel):
    recommendations_created: int
    recommendations: list[OptimizationRecommendationRead]

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

ExperimentStatus = Literal["pending", "running", "completed", "failed"]
Variant = Literal["baseline", "experiment"]
EvaluatorType = Literal["fallback", "deepeval"]


class ExperimentCreate(BaseModel):
    recommendation_id: uuid.UUID | None = None
    name: str
    baseline_config: dict[str, Any]
    experiment_config: dict[str, Any]
    evaluation_dataset_id: uuid.UUID
    # Per-experiment evaluator selection (SDK spec decision - not a
    # project-level setting). "fallback" (default) needs no extra config;
    # "deepeval" requires evaluator_metrics to name at least one supported
    # DeepEval metric (see app.evaluation.deepeval_evaluator._METRIC_NAME_MAP)
    # and the optional `deepeval` package to be installed.
    evaluator_type: EvaluatorType = "fallback"
    evaluator_metrics: list[str] | None = None


class ExperimentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    recommendation_id: uuid.UUID | None
    name: str
    baseline_config: dict[str, Any]
    experiment_config: dict[str, Any]
    evaluation_dataset_id: uuid.UUID
    evaluator_type: EvaluatorType
    evaluator_metrics: list[str] | None
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
    # One entry per metric the experiment's evaluator computed (e.g.
    # {"correctness": -0.02} for the fallback evaluator, or
    # {"faithfulness": -0.01, "answer_relevancy": 0.03} for a
    # multi-metric DeepEval-backed experiment).
    quality_differences: dict[str, float]
    latency_difference_ms: float
    token_reduction_pct: float
    failed_questions: list[str]

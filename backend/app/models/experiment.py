import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Experiment(Base):
    """A controlled run of a Workflow under an alternative configuration,
    compared against baseline on the same EvaluationDataset. See
    docs/adr/0004-experiment-execution-over-http.md for how this is executed
    (over HTTP against the sample app, not in-process)."""

    __tablename__ = "experiments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    recommendation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("optimization_recommendations.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    baseline_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    experiment_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    evaluation_dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_datasets.id"), nullable=False
    )
    # Evaluator selection is per-experiment (SDK spec decision), not a
    # project-level setting - one project can mix DeepEval-backed and
    # fallback-backed experiments. "fallback" = AnswerCorrectnessEvaluator
    # (always available); "deepeval" = DeepEvalEvaluator, requires the
    # optional `deepeval` package and evaluator_metrics to be non-empty.
    evaluator_type: Mapped[str] = mapped_column(String, nullable=False, default="fallback")
    evaluator_metrics: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class ExperimentRun(Base):
    """One variant's (baseline or experiment) aggregated result for an
    Experiment. `metrics` is self-contained and computed directly from the
    evaluation run - it is never written into `traces`/`llm_calls` (explicit
    isolation decision: experiment telemetry is not production telemetry)."""

    __tablename__ = "experiment_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    experiment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("experiments.id"), nullable=False)
    variant: Mapped[str] = mapped_column(String, nullable=False)
    # Keys: cost_per_request, total_cost, avg_input_tokens, avg_output_tokens,
    # avg_latency_ms, quality_scores (dict[str, float], one entry per metric
    # the experiment's evaluator computed - see app.evaluation.Evaluator),
    # request_count (see app.services.experiments for the exact computation).
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class OptimizationRecommendation(Base):
    __tablename__ = "optimization_recommendations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    workflow: Mapped[str | None] = mapped_column(String, nullable=True)
    environment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("environments.id"), nullable=True
    )
    rule_name: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    current_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    proposed_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    estimated_cost_impact: Mapped[str] = mapped_column(Text, nullable=False)
    # Descriptive, pre-experiment JSON blob from the rule engine (Phase 3),
    # kept as-is for backward compatibility. Once a real Experiment is
    # created from this recommendation, `experiment_id` below points at it -
    # the two are independent; an old row may have only the JSON field.
    required_experiment: Mapped[dict] = mapped_column(JSON, nullable=False)
    experiment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("experiments.id"), nullable=True
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    # V2: bucketed HIGH/MEDIUM/LOW view of `confidence`, computed once at
    # analysis time (see app.services.rules.base.bucket_confidence) so the
    # frontend never needs to know the underlying float's thresholds.
    confidence_bucket: Mapped[str | None] = mapped_column(String, nullable=True)
    # V2: structured evidence panel (sample size, avg/p95, ratios, estimated
    # monthly cost, quality_evidence, recommended_next_step) - see
    # app.services.rules.base.build_evidence. Free-form JSON since each rule
    # contributes a different subset of fields.
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # V2: projected dollar range, extrapolated from current aggregate cost x
    # the rule's estimated reduction fraction - deliberately a range, not a
    # single number, since it is a projection rather than a measurement.
    # Null when a rule has no numeric basis for an estimate (e.g. Rules C/D).
    estimated_savings_low: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    estimated_savings_high: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

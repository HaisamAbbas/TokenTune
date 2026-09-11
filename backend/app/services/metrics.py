import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.optimization import OptimizationRecommendation
from app.schemas.metrics import ProjectMetrics
from app.services.cost import aggregate_cost

# Recommendations in these statuses are still "open" - money still sitting
# on the table, not yet decided one way or the other. adopted/rejected are
# terminal and excluded from the potential-savings total.
_OPEN_STATUSES = ("pending", "experiment_created", "experiment_running", "validated")


def get_project_metrics(
    db: Session, project_id: uuid.UUID, from_ts: datetime, to_ts: datetime
) -> ProjectMetrics:
    cost_buckets = aggregate_cost(db, project_id, from_ts, to_ts)
    # With no group_by, aggregate_cost still returns exactly one bucket even
    # when there are zero underlying LLM calls (a plain SQL aggregate over no
    # rows yields one row of NULLs, not zero rows) - so total_cost can be
    # None on that single bucket.
    total_spend = float(cost_buckets[0].total_cost or 0) if cost_buckets else 0.0

    row = (
        db.query(
            func.count(OptimizationRecommendation.id),
            func.sum(OptimizationRecommendation.estimated_savings_low),
            func.sum(OptimizationRecommendation.estimated_savings_high),
        )
        .filter(
            OptimizationRecommendation.project_id == project_id,
            OptimizationRecommendation.status.in_(_OPEN_STATUSES),
        )
        .one()
    )
    open_count, savings_low, savings_high = row

    return ProjectMetrics(
        total_spend=total_spend,
        total_potential_savings_low=float(savings_low or 0),
        total_potential_savings_high=float(savings_high or 0),
        open_opportunity_count=open_count or 0,
    )

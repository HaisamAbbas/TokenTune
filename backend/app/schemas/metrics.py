from pydantic import BaseModel


class ProjectMetrics(BaseModel):
    """V2 project-level dashboard summary: total spend over the requested
    window, plus the total potential savings sitting in currently-open
    (non-terminal) recommendations. Project-scoped only - no cross-project
    rollup exists (see V2 design decisions)."""

    total_spend: float
    total_potential_savings_low: float
    total_potential_savings_high: float
    open_opportunity_count: int

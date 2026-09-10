from app.schemas.optimization import OptimizationRecommendationCreate
from app.services.rules.base import MIN_SAMPLE_SIZE, Rule, WorkflowStats, scaled_confidence

# Above this average number of LLM calls per trace, a workflow likely has
# redundant or consolidatable generation steps. Detection-only: we flag the
# workflow, not any specific step.
CALLS_PER_TRACE_THRESHOLD = 1.5


class UnnecessaryGenerationCallsRule(Rule):
    def evaluate(self, stats: WorkflowStats) -> OptimizationRecommendationCreate | None:
        if stats.trace_count < MIN_SAMPLE_SIZE:
            return None
        if stats.avg_calls_per_trace <= CALLS_PER_TRACE_THRESHOLD:
            return None

        return OptimizationRecommendationCreate(
            project_id=stats.sample_project_id,
            workflow=stats.workflow,
            environment_id=stats.environment_id,
            rule_name="unnecessary_generation_calls",
            reason=(
                f"Workflow makes ~{stats.avg_calls_per_trace:.1f} LLM calls per "
                "trace on average, consider consolidating or removing redundant "
                "steps."
            ),
            current_config={"avg_calls_per_trace": stats.avg_calls_per_trace},
            proposed_config={
                "suggestion": "investigate which steps can be consolidated or removed"
            },
            estimated_cost_impact="depends on which calls, if any, can be removed",
            required_experiment={
                "description": (
                    "Trace through a sample of individual traces for this "
                    "workflow to identify which LLM call steps are redundant."
                )
            },
            confidence=scaled_confidence(stats.trace_count),
        )

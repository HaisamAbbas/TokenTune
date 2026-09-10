from app.services.rules.base import Rule, RuleDetection, WorkflowStats

# Above this average number of LLM calls per trace, a workflow likely has
# redundant or consolidatable generation steps. Detection-only: we flag the
# workflow, not any specific step.
CALLS_PER_TRACE_THRESHOLD = 1.5


class UnnecessaryGenerationCallsRule(Rule):
    def evaluate(self, stats: WorkflowStats) -> RuleDetection | None:
        if stats.avg_calls_per_trace <= CALLS_PER_TRACE_THRESHOLD:
            return None

        return RuleDetection(
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
        )

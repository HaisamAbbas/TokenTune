from app.schemas.optimization import OptimizationRecommendationCreate
from app.services.rules.base import MIN_SAMPLE_SIZE, Rule, WorkflowStats, scaled_confidence

# A prompt (excluding retrieved context) averaging above this many tokens,
# repeated over a high volume of traces, suggests a large static/boilerplate
# prompt worth shrinking or caching rather than per-call variance.
LARGE_PROMPT_TOKEN_THRESHOLD = 2000
# "High call volume" re-uses the same sample-size floor as the other rules -
# by the time trace_count clears MIN_SAMPLE_SIZE we have enough repetitions
# of the same prompt shape to trust the average isn't a fluke.
HIGH_VOLUME_TRACE_COUNT = MIN_SAMPLE_SIZE


class PromptOptimizationRule(Rule):
    def evaluate(self, stats: WorkflowStats) -> OptimizationRecommendationCreate | None:
        if stats.trace_count < MIN_SAMPLE_SIZE:
            return None
        if stats.trace_count < HIGH_VOLUME_TRACE_COUNT:
            return None

        non_retrieval_input_tokens = stats.avg_input_tokens - (stats.avg_retrieval_tokens or 0)
        if non_retrieval_input_tokens <= LARGE_PROMPT_TOKEN_THRESHOLD:
            return None

        return OptimizationRecommendationCreate(
            project_id=stats.sample_project_id,
            workflow=stats.workflow,
            environment_id=stats.environment_id,
            rule_name="prompt_optimization",
            reason=(
                f"Average non-retrieval prompt size is {non_retrieval_input_tokens:.0f} "
                f"tokens across {stats.trace_count} traces, above the "
                f"{LARGE_PROMPT_TOKEN_THRESHOLD}-token threshold - likely a large, "
                "repeated static prompt."
            ),
            current_config={"avg_prompt_tokens": round(non_retrieval_input_tokens)},
            proposed_config={"suggestion": "reduce prompt size or investigate prompt caching"},
            estimated_cost_impact="depends on achievable prompt reduction / cache hit rate",
            required_experiment={
                "description": (
                    "Audit the prompt template for boilerplate that can be "
                    "trimmed or moved to a cached prefix, then re-measure "
                    "average input tokens per call."
                )
            },
            confidence=scaled_confidence(stats.trace_count),
        )

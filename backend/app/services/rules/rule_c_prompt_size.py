from app.services.rules.base import MIN_SAMPLE_SIZE, Rule, RuleDetection, WorkflowStats

# A prompt (excluding retrieved context) averaging above this many tokens,
# repeated over a high volume of traces, suggests a large static/boilerplate
# prompt worth shrinking or caching rather than per-call variance.
LARGE_PROMPT_TOKEN_THRESHOLD = 2000
# "High call volume" re-uses the same sample-size floor as the other rules -
# the engine's MIN_SAMPLE_SIZE gate already guarantees this by the time
# evaluate() is called, so there are enough repetitions of the same prompt
# shape to trust the average isn't a fluke.
HIGH_VOLUME_TRACE_COUNT = MIN_SAMPLE_SIZE


class PromptOptimizationRule(Rule):
    def evaluate(self, stats: WorkflowStats) -> RuleDetection | None:
        non_retrieval_input_tokens = stats.avg_input_tokens - (stats.avg_retrieval_tokens or 0)
        if non_retrieval_input_tokens <= LARGE_PROMPT_TOKEN_THRESHOLD:
            return None

        return RuleDetection(
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
        )

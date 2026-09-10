from app.services.rules.base import Rule, RuleDetection, WorkflowStats

# If retrieved-context tokens make up more than this share of the average
# input prompt, the retrieval step is likely over-fetching.
RETRIEVAL_SHARE_THRESHOLD = 0.4
TOP_K_REDUCTION_FACTOR = 0.4


class ExcessiveRetrievalContextRule(Rule):
    def evaluate(self, stats: WorkflowStats) -> RuleDetection | None:
        if not stats.avg_retrieval_tokens or not stats.avg_input_tokens:
            return None
        if stats.avg_top_k is None:
            return None

        share = stats.avg_retrieval_tokens / stats.avg_input_tokens
        if share <= RETRIEVAL_SHARE_THRESHOLD:
            return None

        current_top_k = round(stats.avg_top_k)
        proposed_top_k = max(1, int(current_top_k * (1 - TOP_K_REDUCTION_FACTOR)))
        if proposed_top_k >= current_top_k:
            return None

        return RuleDetection(
            rule_name="excessive_retrieval_context",
            reason=(
                f"Retrieved context averages {stats.avg_retrieval_tokens:.0f} tokens, "
                f"{share:.0%} of the average input prompt ({stats.avg_input_tokens:.0f} "
                f"tokens) - above the {RETRIEVAL_SHARE_THRESHOLD:.0%} threshold."
            ),
            current_config={"top_k": current_top_k},
            proposed_config={"top_k": proposed_top_k},
            estimated_cost_impact=f"~{share * TOP_K_REDUCTION_FACTOR:.0%} input-token reduction",
            required_experiment={
                "description": (
                    "Re-run the workflow with reduced top_k and compare output "
                    "quality and cost against the current baseline."
                )
            },
        )

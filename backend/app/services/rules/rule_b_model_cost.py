from app.services.pricing import estimate_cost, get_pricing_table
from app.services.rules.base import Rule, RuleDetection, WorkflowStats

REQUIRED_PRICING_KEYS = ("input_per_1k", "output_per_1k")


class ModelCostOptimizationRule(Rule):
    def evaluate(self, stats: WorkflowStats) -> RuleDetection | None:
        if not stats.model_usage:
            return None

        table = get_pricing_table()
        # Dominant model = the one with the most calls in this workflow/env group.
        dominant_model = max(stats.model_usage, key=lambda m: stats.model_usage[m])
        dominant_rates = table.get(dominant_model)
        if dominant_rates is None or not all(
            key in dominant_rates for key in REQUIRED_PRICING_KEYS
        ):
            return None

        dominant_cost = estimate_cost(
            dominant_model, round(stats.avg_input_tokens), round(stats.avg_output_tokens)
        )
        if dominant_cost is None or dominant_cost <= 0:
            return None

        cheaper_candidates = []
        for model, rates in table.items():
            if model == dominant_model:
                continue
            # Skip malformed/partial pricing entries rather than raising -
            # one bad entry shouldn't take down the whole analysis.
            if not all(key in rates for key in REQUIRED_PRICING_KEYS):
                continue
            candidate_cost = estimate_cost(
                model, round(stats.avg_input_tokens), round(stats.avg_output_tokens)
            )
            if candidate_cost is None:
                continue
            if candidate_cost < dominant_cost:
                cheaper_candidates.append((model, candidate_cost))
        if not cheaper_candidates:
            return None

        cheapest_model, cheapest_cost = min(cheaper_candidates, key=lambda item: item[1])
        savings_pct = 1 - (float(cheapest_cost) / float(dominant_cost))

        return RuleDetection(
            rule_name="model_cost_optimization",
            reason=(
                f"Dominant model '{dominant_model}' "
                f"({stats.model_usage[dominant_model]} calls) costs an estimated "
                f"{dominant_cost} per call at current average token usage, while "
                f"'{cheapest_model}' costs an estimated {cheapest_cost} per call."
            ),
            current_config={"model": dominant_model},
            proposed_config={"model": cheapest_model},
            estimated_cost_impact=f"~{savings_pct:.0%} cost reduction per call",
            required_experiment={
                "description": (
                    f"Run an A/B comparison of '{dominant_model}' vs "
                    f"'{cheapest_model}' on this workflow to confirm output "
                    "quality is acceptable before switching."
                )
            },
        )

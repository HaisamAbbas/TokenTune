from app.schemas.optimization import OptimizationRecommendationCreate
from app.services.pricing import get_pricing_table
from app.services.rules.base import MIN_SAMPLE_SIZE, Rule, WorkflowStats, scaled_confidence


class ModelCostOptimizationRule(Rule):
    def evaluate(self, stats: WorkflowStats) -> OptimizationRecommendationCreate | None:
        if stats.trace_count < MIN_SAMPLE_SIZE:
            return None
        if not stats.model_usage:
            return None

        table = get_pricing_table()
        # Dominant model = the one with the most calls in this workflow/env group.
        dominant_model = max(stats.model_usage, key=lambda m: stats.model_usage[m])
        dominant_rates = table.get(dominant_model)
        if dominant_rates is None:
            return None

        cheaper_candidates = [
            (model, rates)
            for model, rates in table.items()
            if model != dominant_model and rates["input_per_1k"] < dominant_rates["input_per_1k"]
        ]
        if not cheaper_candidates:
            return None

        cheapest_model, cheapest_rates = min(
            cheaper_candidates, key=lambda item: item[1]["input_per_1k"]
        )
        savings_pct = 1 - (cheapest_rates["input_per_1k"] / dominant_rates["input_per_1k"])

        return OptimizationRecommendationCreate(
            project_id=stats.sample_project_id,
            workflow=stats.workflow,
            environment_id=stats.environment_id,
            rule_name="model_cost_optimization",
            reason=(
                f"Dominant model '{dominant_model}' "
                f"({stats.model_usage[dominant_model]} calls) costs "
                f"{dominant_rates['input_per_1k']}/1k input tokens, while "
                f"'{cheapest_model}' costs {cheapest_rates['input_per_1k']}/1k."
            ),
            current_config={"model": dominant_model},
            proposed_config={"model": cheapest_model},
            estimated_cost_impact=f"~{savings_pct:.0%} cost reduction on input tokens",
            required_experiment={
                "description": (
                    f"Run an A/B comparison of '{dominant_model}' vs "
                    f"'{cheapest_model}' on this workflow to confirm output "
                    "quality is acceptable before switching."
                )
            },
            confidence=scaled_confidence(stats.trace_count),
        )

from app.schemas.optimization import OptimizationRecommendationCreate
from app.services.rules.base import MIN_SAMPLE_SIZE, Rule, WorkflowStats, scaled_confidence
from app.services.rules.rule_a_retrieval_context import ExcessiveRetrievalContextRule
from app.services.rules.rule_b_model_cost import ModelCostOptimizationRule
from app.services.rules.rule_c_prompt_size import PromptOptimizationRule
from app.services.rules.rule_d_unnecessary_calls import UnnecessaryGenerationCallsRule


class RuleEngine:
    def __init__(self, rules: list[Rule] | None = None) -> None:
        self.rules: list[Rule] = rules or [
            ExcessiveRetrievalContextRule(),
            ModelCostOptimizationRule(),
            PromptOptimizationRule(),
            UnnecessaryGenerationCallsRule(),
        ]

    def run(self, stats: WorkflowStats) -> list[OptimizationRecommendationCreate]:
        # The sample-size gate is enforced once, here, rather than by each
        # rule - below this floor, stats are too noisy for any rule to act on.
        if stats.trace_count < MIN_SAMPLE_SIZE:
            return []

        confidence = scaled_confidence(stats.trace_count)
        results = []
        for rule in self.rules:
            detection = rule.evaluate(stats)
            if detection is None:
                continue
            results.append(
                OptimizationRecommendationCreate(
                    project_id=stats.sample_project_id,
                    workflow=stats.workflow,
                    environment_id=stats.environment_id,
                    rule_name=detection.rule_name,
                    reason=detection.reason,
                    current_config=detection.current_config,
                    proposed_config=detection.proposed_config,
                    estimated_cost_impact=detection.estimated_cost_impact,
                    required_experiment=detection.required_experiment,
                    confidence=confidence,
                )
            )
        return results

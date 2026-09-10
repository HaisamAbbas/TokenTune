from app.schemas.optimization import OptimizationRecommendationCreate
from app.services.rules.base import Rule, WorkflowStats
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
        results = []
        for rule in self.rules:
            recommendation = rule.evaluate(stats)
            if recommendation is not None:
                results.append(recommendation)
        return results

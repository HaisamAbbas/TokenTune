from app.schemas.optimization import OptimizationRecommendationCreate
from app.services.rules.base import (
    MIN_SAMPLE_SIZE,
    Rule,
    WorkflowStats,
    bucket_confidence,
    scaled_confidence,
)
from app.services.rules.rule_a_retrieval_context import ExcessiveRetrievalContextRule
from app.services.rules.rule_b_model_cost import ModelCostOptimizationRule
from app.services.rules.rule_c_prompt_size import PromptOptimizationRule
from app.services.rules.rule_d_unnecessary_calls import UnnecessaryGenerationCallsRule
from app.services.rules.rule_e_segmented_routing import SegmentedModelRoutingRule

# When Rule E finds a meaningful segmented-routing split for a workflow, its
# recommendation is strictly more precise than Rule B's blanket "switch the
# whole workflow" suggestion for the same group - showing both would just be
# contradictory noise. Rule B is suppressed (not run) whenever Rule E fires.
_SEGMENTED_ROUTING_RULE_NAME = "segmented_model_routing"
_MODEL_COST_RULE_NAME = "model_cost_optimization"


class RuleEngine:
    def __init__(self, rules: list[Rule] | None = None) -> None:
        self.rules: list[Rule] = rules or [
            ExcessiveRetrievalContextRule(),
            ModelCostOptimizationRule(),
            PromptOptimizationRule(),
            UnnecessaryGenerationCallsRule(),
            SegmentedModelRoutingRule(),
        ]

    def run(self, stats: WorkflowStats) -> list[OptimizationRecommendationCreate]:
        # The sample-size gate is enforced once, here, rather than by each
        # rule - below this floor, stats are too noisy for any rule to act on.
        if stats.trace_count < MIN_SAMPLE_SIZE:
            return []

        confidence = scaled_confidence(stats.trace_count)
        confidence_bucket = bucket_confidence(confidence)
        detections = []
        for rule in self.rules:
            detection = rule.evaluate(stats)
            if detection is not None:
                detections.append(detection)

        if any(d.rule_name == _SEGMENTED_ROUTING_RULE_NAME for d in detections):
            detections = [d for d in detections if d.rule_name != _MODEL_COST_RULE_NAME]

        return [
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
                confidence_bucket=confidence_bucket,
                evidence=detection.evidence,
                estimated_savings_low=detection.estimated_savings_low,
                estimated_savings_high=detection.estimated_savings_high,
            )
            for detection in detections
        ]

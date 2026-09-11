import uuid

from app.services.rules.base import MIN_SAMPLE_SIZE, Rule, RuleDetection, WorkflowStats
from app.services.rules.engine import RuleEngine


class _AlwaysFiresRule(Rule):
    """A stub rule that always proposes a detection - used to prove the
    engine's MIN_SAMPLE_SIZE gate stops it from ever being called below the
    floor, without needing a real rule's own thresholds to line up."""

    def evaluate(self, stats: WorkflowStats) -> RuleDetection | None:
        return RuleDetection(
            rule_name="model_cost_optimization",
            reason="stub",
            current_config={},
            proposed_config={},
            estimated_cost_impact="stub",
            required_experiment={},
        )


def _stats(**overrides) -> WorkflowStats:
    defaults = {
        "sample_project_id": uuid.uuid4(),
        "workflow": "summarization",
        "environment_id": None,
        "trace_count": MIN_SAMPLE_SIZE,
        "avg_input_tokens": 1000.0,
        "avg_output_tokens": 200.0,
        "avg_retrieval_tokens": None,
        "avg_top_k": None,
        "avg_cost_per_trace": 0.05,
        "model_usage": {"gpt-4o": 50},
        "avg_calls_per_trace": 1.0,
    }
    defaults.update(overrides)
    return WorkflowStats(**defaults)


def test_engine_gates_all_rules_below_min_sample_size() -> None:
    engine = RuleEngine(rules=[_AlwaysFiresRule()])
    stats = _stats(trace_count=MIN_SAMPLE_SIZE - 1)
    assert engine.run(stats) == []


def test_engine_calls_rules_at_min_sample_size() -> None:
    engine = RuleEngine(rules=[_AlwaysFiresRule()])
    stats = _stats(trace_count=MIN_SAMPLE_SIZE)
    results = engine.run(stats)
    assert len(results) == 1


def test_engine_stamps_project_workflow_environment_and_confidence() -> None:
    engine = RuleEngine(rules=[_AlwaysFiresRule()])
    project_id = uuid.uuid4()
    environment_id = uuid.uuid4()
    stats = _stats(
        sample_project_id=project_id,
        workflow="rag-workflow",
        environment_id=environment_id,
        trace_count=MIN_SAMPLE_SIZE * 4,
    )
    [recommendation] = engine.run(stats)
    assert recommendation.project_id == project_id
    assert recommendation.workflow == "rag-workflow"
    assert recommendation.environment_id == environment_id
    assert recommendation.confidence == 1.0
    assert recommendation.confidence_bucket == "high"


class _AlwaysFiresModelCostRule(Rule):
    def evaluate(self, stats: WorkflowStats) -> RuleDetection | None:
        return RuleDetection(
            rule_name="model_cost_optimization",
            reason="stub",
            current_config={},
            proposed_config={},
            estimated_cost_impact="stub",
            required_experiment={},
        )


class _AlwaysFiresSegmentedRoutingRule(Rule):
    def evaluate(self, stats: WorkflowStats) -> RuleDetection | None:
        return RuleDetection(
            rule_name="segmented_model_routing",
            reason="stub",
            current_config={},
            proposed_config={},
            estimated_cost_impact="stub",
            required_experiment={},
        )


def test_engine_suppresses_model_cost_when_segmented_routing_fires() -> None:
    engine = RuleEngine(rules=[_AlwaysFiresModelCostRule(), _AlwaysFiresSegmentedRoutingRule()])
    stats = _stats()
    results = engine.run(stats)
    rule_names = {r.rule_name for r in results}
    assert rule_names == {"segmented_model_routing"}


def test_engine_keeps_model_cost_when_segmented_routing_does_not_fire() -> None:
    engine = RuleEngine(rules=[_AlwaysFiresModelCostRule()])
    stats = _stats()
    results = engine.run(stats)
    rule_names = {r.rule_name for r in results}
    assert rule_names == {"model_cost_optimization"}

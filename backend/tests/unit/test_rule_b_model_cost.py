import uuid

from app.services.rules.base import MIN_SAMPLE_SIZE, WorkflowStats
from app.services.rules.rule_b_model_cost import ModelCostOptimizationRule

RULE = ModelCostOptimizationRule()


def _stats(**overrides) -> WorkflowStats:
    defaults = {
        "sample_project_id": uuid.uuid4(),
        "workflow": "summarization",
        "environment_id": None,
        "trace_count": 50,
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


def test_fires_when_dominant_model_has_cheaper_alternative() -> None:
    stats = _stats(model_usage={"gpt-4o": 40, "gpt-4o-mini": 10})
    recommendation = RULE.evaluate(stats)
    assert recommendation is not None
    assert recommendation.rule_name == "model_cost_optimization"
    assert recommendation.current_config["model"] == "gpt-4o"
    assert recommendation.proposed_config["model"] == "gpt-4o-mini"


def test_does_not_fire_when_dominant_model_is_already_cheapest() -> None:
    stats = _stats(model_usage={"gpt-4o-mini": 50})
    assert RULE.evaluate(stats) is None


def test_does_not_fire_below_min_sample_size() -> None:
    stats = _stats(trace_count=MIN_SAMPLE_SIZE - 1, model_usage={"gpt-4o": 5})
    assert RULE.evaluate(stats) is None

import uuid

from app.services.rules.base import WorkflowStats
from app.services.rules.rule_d_unnecessary_calls import UnnecessaryGenerationCallsRule

RULE = UnnecessaryGenerationCallsRule()


def _stats(**overrides) -> WorkflowStats:
    defaults = {
        "sample_project_id": uuid.uuid4(),
        "workflow": "agent-workflow",
        "environment_id": None,
        "trace_count": 50,
        "avg_input_tokens": 1000.0,
        "avg_output_tokens": 200.0,
        "avg_retrieval_tokens": None,
        "avg_top_k": None,
        "avg_cost_per_trace": 0.05,
        "model_usage": {"gpt-4o": 100},
        "avg_calls_per_trace": 2.5,
    }
    defaults.update(overrides)
    return WorkflowStats(**defaults)


def test_fires_when_calls_per_trace_exceeds_threshold() -> None:
    stats = _stats(avg_calls_per_trace=2.5)
    recommendation = RULE.evaluate(stats)
    assert recommendation is not None
    assert recommendation.rule_name == "unnecessary_generation_calls"


def test_does_not_fire_below_calls_per_trace_threshold() -> None:
    stats = _stats(avg_calls_per_trace=1.2)
    assert RULE.evaluate(stats) is None

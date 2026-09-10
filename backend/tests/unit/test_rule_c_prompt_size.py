import uuid

from app.services.rules.base import MIN_SAMPLE_SIZE, WorkflowStats
from app.services.rules.rule_c_prompt_size import PromptOptimizationRule

RULE = PromptOptimizationRule()


def _stats(**overrides) -> WorkflowStats:
    defaults = {
        "sample_project_id": uuid.uuid4(),
        "workflow": "summarization",
        "environment_id": None,
        "trace_count": 50,
        "avg_input_tokens": 3000.0,
        "avg_output_tokens": 200.0,
        "avg_retrieval_tokens": None,
        "avg_top_k": None,
        "avg_cost_per_trace": 0.05,
        "model_usage": {"gpt-4o": 50},
        "avg_calls_per_trace": 1.0,
    }
    defaults.update(overrides)
    return WorkflowStats(**defaults)


def test_fires_when_prompt_is_large_and_repeated() -> None:
    stats = _stats(avg_input_tokens=3000.0, avg_retrieval_tokens=None)
    recommendation = RULE.evaluate(stats)
    assert recommendation is not None
    assert recommendation.rule_name == "prompt_optimization"


def test_does_not_fire_below_prompt_size_threshold() -> None:
    stats = _stats(avg_input_tokens=1000.0)
    assert RULE.evaluate(stats) is None


def test_does_not_fire_below_min_sample_size() -> None:
    stats = _stats(trace_count=MIN_SAMPLE_SIZE - 1, avg_input_tokens=5000.0)
    assert RULE.evaluate(stats) is None

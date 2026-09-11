import uuid

from app.services.rules.base import WorkflowStats
from app.services.rules.rule_a_retrieval_context import ExcessiveRetrievalContextRule

RULE = ExcessiveRetrievalContextRule()


def _stats(**overrides) -> WorkflowStats:
    defaults = {
        "sample_project_id": uuid.uuid4(),
        "workflow": "rag-workflow",
        "environment_id": None,
        "trace_count": 50,
        "avg_input_tokens": 1000.0,
        "avg_output_tokens": 200.0,
        "avg_retrieval_tokens": 500.0,
        "avg_top_k": 20.0,
        "avg_cost_per_trace": 0.05,
        "model_usage": {"gpt-4o": 50},
        "avg_calls_per_trace": 1.0,
    }
    defaults.update(overrides)
    return WorkflowStats(**defaults)


def test_fires_when_retrieval_share_exceeds_threshold() -> None:
    stats = _stats(avg_retrieval_tokens=500.0, avg_input_tokens=1000.0)  # 50% share
    recommendation = RULE.evaluate(stats)
    assert recommendation is not None
    assert recommendation.rule_name == "excessive_retrieval_context"
    assert recommendation.proposed_config["top_k"] < recommendation.current_config["top_k"]


def test_fires_with_evidence_and_savings_estimate() -> None:
    stats = _stats(
        avg_retrieval_tokens=500.0,
        avg_input_tokens=1000.0,
        avg_cost_per_trace=1.0,
        trace_count=100,
        window_days=30.0,
    )  # 50% share, $100/mo baseline
    recommendation = RULE.evaluate(stats)
    assert recommendation is not None
    assert recommendation.evidence is not None
    assert recommendation.evidence["sample_size"] == 100
    assert recommendation.evidence["ratio"] == 0.5
    assert recommendation.evidence["quality_evidence"] == "not_yet_tested"
    assert recommendation.evidence["estimated_monthly_cost"] == 100.0
    assert recommendation.estimated_savings_low is not None
    assert recommendation.estimated_savings_high is not None
    assert recommendation.estimated_savings_low < recommendation.estimated_savings_high


def test_does_not_fire_below_share_threshold() -> None:
    stats = _stats(avg_retrieval_tokens=200.0, avg_input_tokens=1000.0)  # 20% share
    assert RULE.evaluate(stats) is None

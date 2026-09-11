import uuid

from app.services.rules.base import WorkflowStats
from app.services.rules.rule_e_segmented_routing import SegmentedModelRoutingRule

RULE = SegmentedModelRoutingRule()


def _stats(**overrides) -> WorkflowStats:
    defaults = {
        "sample_project_id": uuid.uuid4(),
        "workflow": "rag-workflow",
        "environment_id": None,
        "trace_count": 100,
        "avg_input_tokens": 1000.0,
        "avg_output_tokens": 200.0,
        "avg_retrieval_tokens": None,
        "avg_top_k": None,
        "avg_cost_per_trace": 0.05,
        "model_usage": {"gpt-4o": 100},
        "avg_calls_per_trace": 1.0,
        "segments": None,
    }
    defaults.update(overrides)
    return WorkflowStats(**defaults)


def _segment(trace_count: int, model_usage: dict[str, int], **overrides) -> WorkflowStats:
    return _stats(trace_count=trace_count, model_usage=model_usage, segments=None, **overrides)


def test_does_not_fire_without_segments() -> None:
    stats = _stats(segments=None)
    assert RULE.evaluate(stats) is None


def test_fires_when_simple_segment_has_cheaper_alternative() -> None:
    simple = _segment(30, {"gpt-4o": 30}, avg_input_tokens=200.0, avg_output_tokens=50.0)
    complex_ = _segment(70, {"gpt-4o": 70}, avg_input_tokens=2000.0, avg_output_tokens=400.0)
    stats = _stats(trace_count=100, segments={"simple": simple, "complex": complex_})

    recommendation = RULE.evaluate(stats)
    assert recommendation is not None
    assert recommendation.rule_name == "segmented_model_routing"
    assert recommendation.current_config["model"] == "gpt-4o"
    assert recommendation.proposed_config["simple_segment_model"] == "gpt-4o-mini"
    assert recommendation.proposed_config["complex_segment_model"] == "gpt-4o"
    assert recommendation.evidence is not None
    assert recommendation.evidence["ratio"] == 0.3


def test_does_not_fire_when_simple_segment_share_too_small() -> None:
    simple = _segment(5, {"gpt-4o": 5}, avg_input_tokens=200.0, avg_output_tokens=50.0)
    complex_ = _segment(95, {"gpt-4o": 95}, avg_input_tokens=2000.0, avg_output_tokens=400.0)
    stats = _stats(trace_count=100, segments={"simple": simple, "complex": complex_})
    assert RULE.evaluate(stats) is None


def test_does_not_fire_when_dominant_model_already_cheapest() -> None:
    simple = _segment(30, {"gpt-4o-mini": 30}, avg_input_tokens=200.0, avg_output_tokens=50.0)
    complex_ = _segment(70, {"gpt-4o-mini": 70}, avg_input_tokens=2000.0, avg_output_tokens=400.0)
    stats = _stats(trace_count=100, segments={"simple": simple, "complex": complex_})
    assert RULE.evaluate(stats) is None

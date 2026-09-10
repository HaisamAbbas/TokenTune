import uuid
from decimal import Decimal

import pytest

from app.services.rules import rule_b_model_cost
from app.services.rules.base import WorkflowStats
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


def test_does_not_fire_when_cheaper_input_rate_is_pricier_overall(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A model with a lower input_per_1k rate but a much higher output_per_1k
    rate can end up costing MORE per call once output tokens are counted -
    it must not be recommended as "cheaper"."""
    table = {
        "dominant-model": {"input_per_1k": 0.005, "output_per_1k": 0.01},
        # Cheaper on input, but so much pricier on output that total cost at
        # this workflow's average token usage is higher overall.
        "input-cheap-model": {"input_per_1k": 0.001, "output_per_1k": 0.2},
    }
    monkeypatch.setattr(rule_b_model_cost, "get_pricing_table", lambda: table)

    def fake_estimate_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal | None:
        rates = table.get(model)
        if rates is None:
            return None
        return (Decimal(input_tokens) / 1000) * Decimal(str(rates["input_per_1k"])) + (
            Decimal(output_tokens) / 1000
        ) * Decimal(str(rates["output_per_1k"]))

    monkeypatch.setattr(rule_b_model_cost, "estimate_cost", fake_estimate_cost)

    stats = _stats(
        model_usage={"dominant-model": 50},
        avg_input_tokens=1000.0,
        avg_output_tokens=200.0,
    )
    assert RULE.evaluate(stats) is None


def test_skips_malformed_pricing_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    table = {
        "gpt-4o": {"input_per_1k": 0.0025, "output_per_1k": 0.01},
        "gpt-4o-mini": {"input_per_1k": 0.00015, "output_per_1k": 0.0006},
        # Malformed: missing output_per_1k. Should be skipped, not raise.
        "broken-model": {"input_per_1k": 0.0001},
    }
    monkeypatch.setattr(rule_b_model_cost, "get_pricing_table", lambda: table)

    def fake_estimate_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal | None:
        rates = table.get(model)
        if rates is None or "input_per_1k" not in rates or "output_per_1k" not in rates:
            return None
        return (Decimal(input_tokens) / 1000) * Decimal(str(rates["input_per_1k"])) + (
            Decimal(output_tokens) / 1000
        ) * Decimal(str(rates["output_per_1k"]))

    monkeypatch.setattr(rule_b_model_cost, "estimate_cost", fake_estimate_cost)

    stats = _stats(model_usage={"gpt-4o": 50})
    recommendation = RULE.evaluate(stats)
    assert recommendation is not None
    assert recommendation.proposed_config["model"] == "gpt-4o-mini"

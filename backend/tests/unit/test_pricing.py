from decimal import Decimal

from app.services.pricing import estimate_cost


def test_estimate_cost_known_model() -> None:
    cost = estimate_cost("gpt-4o-mini", input_tokens=1000, output_tokens=1000)
    assert cost == Decimal("0.00015") + Decimal("0.0006")


def test_estimate_cost_unknown_model_returns_none() -> None:
    assert estimate_cost("some-unlisted-model", input_tokens=100, output_tokens=100) is None

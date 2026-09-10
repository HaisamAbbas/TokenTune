import pytest

from app.models.experiment import ExperimentRun
from app.services.experiments import compare_runs


def _run(variant: str, **metrics: float) -> ExperimentRun:
    return ExperimentRun(experiment_id=None, variant=variant, metrics=metrics)  # type: ignore[arg-type]


def test_compare_runs_computes_reductions_and_differences() -> None:
    baseline = _run(
        "baseline",
        cost_per_request=0.01,
        total_cost=1.0,
        avg_input_tokens=800.0,
        avg_output_tokens=200.0,
        avg_latency_ms=500.0,
        quality_score=0.9,
        request_count=100,
    )
    experiment = _run(
        "experiment",
        cost_per_request=0.006,
        total_cost=0.6,
        avg_input_tokens=500.0,
        avg_output_tokens=200.0,
        avg_latency_ms=400.0,
        quality_score=0.85,
        request_count=100,
    )

    result = compare_runs(baseline, experiment)

    assert result["cost_reduction_pct"] == pytest.approx(40.0)
    assert result["quality_difference"] == pytest.approx(-0.05)
    assert result["latency_difference_ms"] == pytest.approx(-100.0)
    assert result["token_reduction_pct"] == pytest.approx(30.0)


def test_compare_runs_handles_zero_baseline_cost_without_division_error() -> None:
    baseline = _run(
        "baseline",
        cost_per_request=0.0,
        total_cost=0.0,
        avg_input_tokens=0.0,
        avg_output_tokens=0.0,
        avg_latency_ms=0.0,
        quality_score=0.0,
        request_count=0,
    )
    experiment = _run(
        "experiment",
        cost_per_request=0.01,
        total_cost=1.0,
        avg_input_tokens=100.0,
        avg_output_tokens=50.0,
        avg_latency_ms=300.0,
        quality_score=0.5,
        request_count=10,
    )

    result = compare_runs(baseline, experiment)

    assert result["cost_reduction_pct"] == 0.0
    assert result["token_reduction_pct"] == 0.0
    assert result["quality_difference"] == pytest.approx(0.5)
    assert result["latency_difference_ms"] == pytest.approx(300.0)


def test_compare_runs_cost_increase_is_negative_reduction() -> None:
    baseline = _run(
        "baseline",
        cost_per_request=0.005,
        total_cost=0.5,
        avg_input_tokens=400.0,
        avg_output_tokens=100.0,
        avg_latency_ms=300.0,
        quality_score=0.7,
        request_count=50,
    )
    experiment = _run(
        "experiment",
        cost_per_request=0.01,
        total_cost=1.0,
        avg_input_tokens=400.0,
        avg_output_tokens=100.0,
        avg_latency_ms=300.0,
        quality_score=0.9,
        request_count=50,
    )

    result = compare_runs(baseline, experiment)

    assert result["cost_reduction_pct"] == pytest.approx(-100.0)
    assert result["quality_difference"] == pytest.approx(0.2)

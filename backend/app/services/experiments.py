import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.evaluation import AnswerCorrectnessEvaluator, Evaluator
from app.models.evaluation import EvaluationDataset, EvaluationItem
from app.models.experiment import Experiment, ExperimentRun
from app.models.optimization import OptimizationRecommendation
from app.models.project import Project
from app.services.pricing import estimate_cost

# The model used for the outer /api/chat request body. A per-variant
# `config_override.model` (when set) takes precedence inside the sample app
# - see OptimizerClient.get_config() - so this is just the fallback the
# sample app would otherwise use.
_DEFAULT_MODEL = "glm-4.5-flash"


@dataclass
class _ItemResult:
    input_tokens: int
    output_tokens: int
    latency_ms: float
    quality_score: float


@dataclass
class _VariantOutcome:
    metrics: dict[str, float | int]
    failed_questions: list[str] = field(default_factory=list)


@dataclass
class ExperimentOutcome:
    """Return value of `run_experiment`: the (now completed/failed)
    Experiment, its two persisted ExperimentRun rows, and the derived
    comparison numbers."""

    experiment: Experiment
    baseline_run: ExperimentRun
    experiment_run: ExperimentRun
    cost_reduction_pct: float
    quality_difference: float
    latency_difference_ms: float
    token_reduction_pct: float
    failed_questions: list[str]


def create_experiment(
    db: Session,
    project: Project,
    baseline_config: dict,
    experiment_config: dict,
    evaluation_dataset: EvaluationDataset,
    name: str,
    recommendation: OptimizationRecommendation | None = None,
) -> Experiment:
    """Persist a new Experiment in `pending` status.

    If created from a recommendation, links the recommendation to this
    experiment via `OptimizationRecommendation.experiment_id` (the FK added
    in Phase 5 alongside the pre-existing `required_experiment` JSON field).
    """
    experiment = Experiment(
        project_id=project.id,
        recommendation_id=recommendation.id if recommendation else None,
        name=name,
        baseline_config=baseline_config,
        experiment_config=experiment_config,
        evaluation_dataset_id=evaluation_dataset.id,
        status="pending",
    )
    db.add(experiment)
    db.flush()

    if recommendation is not None:
        recommendation.experiment_id = experiment.id

    db.commit()
    db.refresh(experiment)
    return experiment


async def _run_variant(
    client: httpx.AsyncClient,
    evaluator: Evaluator,
    items: list[EvaluationItem],
    config_override: dict,
) -> _VariantOutcome:
    results: list[_ItemResult] = []
    failed_questions: list[str] = []
    total_cost = 0.0

    for item in items:
        try:
            start = time.perf_counter()
            response = await client.post(
                "/api/chat",
                json={
                    "model": _DEFAULT_MODEL,
                    "messages": [{"role": "user", "content": item.question}],
                    "config_override": config_override,
                },
            )
            latency_ms = (time.perf_counter() - start) * 1000
            response.raise_for_status()
            body = response.json()
            actual_answer = body.get("response", "")
            usage = body.get("usage") or {}
            input_tokens = int(usage.get("prompt_tokens", 0))
            output_tokens = int(usage.get("completion_tokens", 0))

            quality_score = await evaluator.evaluate(
                question=item.question,
                expected_answer=item.expected_answer,
                actual_answer=actual_answer,
            )

            model_for_cost = config_override.get("model") or _DEFAULT_MODEL
            cost = estimate_cost(model_for_cost, input_tokens, output_tokens)
            if cost is not None:
                total_cost += float(cost)

            results.append(
                _ItemResult(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    quality_score=quality_score,
                )
            )
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            # Don't let one bad question kill the whole run - record it and
            # keep going, aggregating over whatever succeeded.
            failed_questions.append(f"{item.question!r}: {exc}")

    request_count = len(results)
    if request_count == 0:
        return _VariantOutcome(
            metrics={
                "cost_per_request": 0.0,
                "total_cost": 0.0,
                "avg_input_tokens": 0.0,
                "avg_output_tokens": 0.0,
                "avg_latency_ms": 0.0,
                "quality_score": 0.0,
                "request_count": 0,
            },
            failed_questions=failed_questions,
        )

    metrics = {
        "cost_per_request": total_cost / request_count,
        "total_cost": total_cost,
        "avg_input_tokens": sum(r.input_tokens for r in results) / request_count,
        "avg_output_tokens": sum(r.output_tokens for r in results) / request_count,
        "avg_latency_ms": sum(r.latency_ms for r in results) / request_count,
        "quality_score": sum(r.quality_score for r in results) / request_count,
        "request_count": request_count,
    }
    return _VariantOutcome(metrics=metrics, failed_questions=failed_questions)


async def run_experiment(
    db: Session,
    experiment: Experiment,
    _http_client: httpx.AsyncClient | None = None,
    _evaluator: Evaluator | None = None,
) -> ExperimentOutcome:
    """Execute both variants of `experiment` against the sample app over
    HTTP (see docs/adr/0004), score each answer with the Answer Correctness
    evaluator, persist one ExperimentRun per variant, and return the
    comparison. Never raises for per-item failures; only raises if the
    dataset itself has no items or every item in a variant fails (in which
    case the experiment is marked `failed` and the exception is not
    propagated - the returned dict carries `experiment.status == "failed"`
    via the caller re-reading the row, callers should check `experiment.status`).
    """
    evaluator = _evaluator or AnswerCorrectnessEvaluator()
    items = (
        db.query(EvaluationItem)
        .filter(EvaluationItem.dataset_id == experiment.evaluation_dataset_id)
        .all()
    )

    experiment.status = "running"
    db.commit()

    if not items:
        experiment.status = "failed"
        experiment.error = "evaluation dataset has no items"
        db.commit()
        raise ValueError(experiment.error)

    owns_client = _http_client is None
    client = _http_client or httpx.AsyncClient(base_url=settings.sample_rag_app_url, timeout=60.0)
    try:
        baseline_outcome = await _run_variant(client, evaluator, items, experiment.baseline_config)
        experiment_outcome = await _run_variant(
            client, evaluator, items, experiment.experiment_config
        )
    finally:
        if owns_client:
            await client.aclose()

    all_failures = baseline_outcome.failed_questions + experiment_outcome.failed_questions
    now = datetime.now(UTC)

    baseline_row = ExperimentRun(
        experiment_id=experiment.id,
        variant="baseline",
        metrics=baseline_outcome.metrics,
        completed_at=now,
    )
    experiment_row = ExperimentRun(
        experiment_id=experiment.id,
        variant="experiment",
        metrics=experiment_outcome.metrics,
        completed_at=now,
    )
    db.add(baseline_row)
    db.add(experiment_row)

    if baseline_outcome.metrics["request_count"] == 0 or (
        experiment_outcome.metrics["request_count"] == 0
    ):
        experiment.status = "failed"
        experiment.error = "all evaluation items failed for a variant: " + "; ".join(all_failures)
    else:
        experiment.status = "completed"

    db.commit()
    db.refresh(baseline_row)
    db.refresh(experiment_row)
    db.refresh(experiment)

    comparison = compare_runs(baseline_row, experiment_row)
    return ExperimentOutcome(
        experiment=experiment,
        baseline_run=baseline_row,
        experiment_run=experiment_row,
        cost_reduction_pct=comparison["cost_reduction_pct"],
        quality_difference=comparison["quality_difference"],
        latency_difference_ms=comparison["latency_difference_ms"],
        token_reduction_pct=comparison["token_reduction_pct"],
        failed_questions=all_failures,
    )


def compare_runs(baseline_run: ExperimentRun, experiment_run: ExperimentRun) -> dict:
    """Compute the comparison numbers the platform's success criteria are
    stated in terms of, from two already-persisted ExperimentRun rows."""
    baseline = baseline_run.metrics
    experiment = experiment_run.metrics

    baseline_cost = float(baseline["total_cost"])
    experiment_cost = float(experiment["total_cost"])
    cost_reduction_pct = (
        (baseline_cost - experiment_cost) / baseline_cost * 100 if baseline_cost > 0 else 0.0
    )

    baseline_tokens = float(baseline["avg_input_tokens"]) + float(baseline["avg_output_tokens"])
    experiment_tokens = float(experiment["avg_input_tokens"]) + float(
        experiment["avg_output_tokens"]
    )
    token_reduction_pct = (
        (baseline_tokens - experiment_tokens) / baseline_tokens * 100
        if baseline_tokens > 0
        else 0.0
    )

    quality_difference = float(experiment["quality_score"]) - float(baseline["quality_score"])
    latency_difference_ms = float(experiment["avg_latency_ms"]) - float(baseline["avg_latency_ms"])

    return {
        "cost_reduction_pct": cost_reduction_pct,
        "quality_difference": quality_difference,
        "latency_difference_ms": latency_difference_ms,
        "token_reduction_pct": token_reduction_pct,
    }

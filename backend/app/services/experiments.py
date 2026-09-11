import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.evaluation import AnswerCorrectnessEvaluator, DeepEvalEvaluator, Evaluator
from app.models.evaluation import EvaluationDataset, EvaluationItem
from app.models.experiment import Experiment, ExperimentRun
from app.models.optimization import OptimizationRecommendation
from app.models.project import Project
from app.services.pricing import estimate_cost
from app.services.rules.base import QUALITY_VALIDATION_THRESHOLD

# Lifecycle states a linked recommendation is still safe to auto-advance
# from. A human's explicit "adopted"/"rejected" decision (via PATCH
# .../optimizations/{id}) is never overwritten by these automatic
# transitions - see _advance_recommendation_lifecycle below.
_AUTO_ADVANCEABLE_STATUSES = {"pending", "experiment_created", "experiment_running"}


def _advance_recommendation_lifecycle(
    db: Session, recommendation: OptimizationRecommendation | None, new_status: str
) -> None:
    """Move a linked recommendation's status forward automatically, as a
    side effect of backend-observable facts (an experiment was created / is
    running / completed) - never as a manual PATCH. Never overwrites a
    human's adopted/rejected decision."""
    if recommendation is None:
        return
    if recommendation.status not in _AUTO_ADVANCEABLE_STATUSES:
        return
    recommendation.status = new_status

logger = logging.getLogger(__name__)

# The model used for the outer /api/chat request body. A per-variant
# `config_override.model` (when set) takes precedence inside the sample app
# - see OptimizerClient.get_config() - so this is just the fallback the
# sample app would otherwise use.
_DEFAULT_MODEL = "glm-4.5-flash"

# Upper bound on concurrent in-flight /api/chat + judge calls per variant.
# Originally 5; lowered to 2 after a real run against z.ai's free
# glm-4.5-flash tier showed 5 concurrent items (each potentially retrying)
# still saturated that tier's rate limit even with backoff. 2 is a
# conservative bound for constrained/free providers - still faster than
# strictly sequential, but a project on a higher-throughput provider/tier
# may want this configurable in a later phase rather than hardcoded.
_MAX_CONCURRENT_ITEMS = 2

# A 429 from the underlying LLM provider (e.g. a free-tier model's rate
# limit) is transient, not a real failure of the item - discovered when
# _MAX_CONCURRENT_ITEMS's concurrency tripped z.ai's free glm-4.5-flash tier
# rate limit during a real run. Retry a bounded number of times with
# exponential backoff + jitter before giving up on the item.
_RATE_LIMIT_MAX_RETRIES = 3
_RATE_LIMIT_BASE_DELAY_SECONDS = 2.0


@dataclass
class _ItemResult:
    input_tokens: int
    output_tokens: int
    latency_ms: float
    quality_scores: dict[str, float]


@dataclass
class _VariantOutcome:
    metrics: dict[str, Any]
    failed_questions: list[str] = field(default_factory=list)


@dataclass
class ExperimentOutcome:
    """Return value of `run_experiment`: the (now completed/failed)
    Experiment, its two persisted ExperimentRun rows, and - only when the
    experiment actually completed - the derived comparison numbers.

    When `experiment.status == "failed"` (e.g. every item in a variant
    failed), the comparison fields are all `None`: they are never computed
    against a meaningless all-zero/all-failed baseline. Callers must check
    `experiment.status` before trusting them.
    """

    experiment: Experiment
    baseline_run: ExperimentRun
    experiment_run: ExperimentRun
    cost_reduction_pct: float | None
    quality_differences: dict[str, float] | None
    latency_difference_ms: float | None
    token_reduction_pct: float | None
    failed_questions: list[str]


def _resolve_evaluator(experiment: Experiment) -> Evaluator:
    """Per-experiment evaluator selection (SDK spec decision): `evaluator_type`
    on the Experiment row decides which Evaluator implementation runs, never
    a project-level setting."""
    if experiment.evaluator_type == "deepeval":
        if not experiment.evaluator_metrics:
            raise ValueError(
                "experiment.evaluator_type is 'deepeval' but evaluator_metrics is empty"
            )
        return DeepEvalEvaluator(experiment.evaluator_metrics)
    return AnswerCorrectnessEvaluator()


def create_experiment(
    db: Session,
    project: Project,
    baseline_config: dict,
    experiment_config: dict,
    evaluation_dataset: EvaluationDataset,
    name: str,
    recommendation: OptimizationRecommendation | None = None,
    evaluator_type: str = "fallback",
    evaluator_metrics: list[str] | None = None,
) -> Experiment:
    """Persist a new Experiment in `pending` status.

    If created from a recommendation, links the recommendation to this
    experiment via `OptimizationRecommendation.experiment_id` (the FK added
    in Phase 5 alongside the pre-existing `required_experiment` JSON field).
    """
    if evaluator_type == "deepeval" and not evaluator_metrics:
        raise ValueError("evaluator_metrics must be non-empty when evaluator_type is 'deepeval'")

    experiment = Experiment(
        project_id=project.id,
        recommendation_id=recommendation.id if recommendation else None,
        name=name,
        baseline_config=baseline_config,
        experiment_config=experiment_config,
        evaluation_dataset_id=evaluation_dataset.id,
        evaluator_type=evaluator_type,
        evaluator_metrics=evaluator_metrics,
        status="pending",
    )
    db.add(experiment)
    db.flush()

    if recommendation is not None:
        recommendation.experiment_id = experiment.id
        _advance_recommendation_lifecycle(db, recommendation, "experiment_created")

    db.commit()
    db.refresh(experiment)
    return experiment


def _get_linked_recommendation(
    db: Session, experiment: Experiment
) -> OptimizationRecommendation | None:
    return (
        db.query(OptimizationRecommendation)
        .filter(OptimizationRecommendation.experiment_id == experiment.id)
        .first()
    )


async def _run_item(
    client: httpx.AsyncClient,
    evaluator: Evaluator,
    item: EvaluationItem,
    config_override: dict,
    semaphore: asyncio.Semaphore,
) -> tuple[_ItemResult, float] | str:
    """Run a single evaluation item and return its `(_ItemResult, cost)`, or
    a string describing the failure. Never raises - each item's failure is
    fully independent so one bad item can't cancel its siblings under
    `asyncio.gather`."""
    async with semaphore:
        for attempt in range(_RATE_LIMIT_MAX_RETRIES + 1):
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

                quality_scores = await evaluator.evaluate(
                    question=item.question,
                    expected_answer=item.expected_answer,
                    actual_answer=actual_answer,
                )

                model_for_cost = config_override.get("model") or _DEFAULT_MODEL
                cost = estimate_cost(model_for_cost, input_tokens, output_tokens)

                item_result = _ItemResult(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    quality_scores=quality_scores,
                )
                return item_result, float(cost) if cost is not None else 0.0
            except httpx.HTTPStatusError as exc:
                # The sample app doesn't propagate the underlying provider's
                # 429 as a 429 - an unhandled openai.RateLimitError inside
                # its own request handler surfaces to us as a plain 500 (its
                # default FastAPI exception handler), discovered for real
                # under _MAX_CONCURRENT_ITEMS concurrency against z.ai's free
                # glm-4.5-flash tier. Treat any 429 or 5xx from the sample
                # app as transient and worth retrying, not just a literal 429.
                is_transient = exc.response.status_code == 429 or exc.response.status_code >= 500
                if is_transient and attempt < _RATE_LIMIT_MAX_RETRIES:
                    delay = _RATE_LIMIT_BASE_DELAY_SECONDS * (2**attempt) + random.uniform(0, 1)
                    logger.warning(
                        "transient error (%d) on %r (attempt %d/%d), retrying in %.1fs",
                        exc.response.status_code,
                        item.question,
                        attempt + 1,
                        _RATE_LIMIT_MAX_RETRIES,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.warning(
                    "evaluation item failed: %r: %s", item.question, exc, exc_info=True
                )
                return f"{item.question!r}: {exc}"
            except httpx.TimeoutException as exc:
                # Discovered for real: under load (rate-limit retries piling
                # up inside the sample app's own downstream call), our
                # client-to-sample-app request itself can time out with no
                # response at all - a different exception type than the
                # HTTPStatusError case above (no response object exists), so
                # it needs its own transient-retry branch.
                if attempt < _RATE_LIMIT_MAX_RETRIES:
                    delay = _RATE_LIMIT_BASE_DELAY_SECONDS * (2**attempt) + random.uniform(0, 1)
                    logger.warning(
                        "timeout on %r (attempt %d/%d), retrying in %.1fs",
                        item.question,
                        attempt + 1,
                        _RATE_LIMIT_MAX_RETRIES,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.warning(
                    "evaluation item failed: %r: %s", item.question, exc, exc_info=True
                )
                return f"{item.question!r}: {exc}"
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                # Don't let one bad question kill the whole run - record it
                # and keep going, aggregating over whatever succeeded.
                logger.warning(
                    "evaluation item failed: %r: %s", item.question, exc, exc_info=True
                )
                return f"{item.question!r}: {exc}"
        # Unreachable: the loop above always returns or continues, and the
        # last iteration (attempt == _RATE_LIMIT_MAX_RETRIES) never continues.
        raise AssertionError("unreachable")


async def _run_variant(
    client: httpx.AsyncClient,
    evaluator: Evaluator,
    items: list[EvaluationItem],
    config_override: dict,
) -> _VariantOutcome:
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_ITEMS)
    outcomes = await asyncio.gather(
        *(_run_item(client, evaluator, item, config_override, semaphore) for item in items)
    )

    results: list[_ItemResult] = []
    failed_questions: list[str] = []
    total_cost = 0.0
    for outcome in outcomes:
        if isinstance(outcome, str):
            failed_questions.append(outcome)
            continue
        item_result, item_cost = outcome
        results.append(item_result)
        total_cost += item_cost

    request_count = len(results)
    if request_count == 0:
        return _VariantOutcome(
            metrics={
                "cost_per_request": 0.0,
                "total_cost": 0.0,
                "avg_input_tokens": 0.0,
                "avg_output_tokens": 0.0,
                "avg_latency_ms": 0.0,
                "quality_scores": {},
                "request_count": 0,
                "failed_questions": failed_questions,
            },
            failed_questions=failed_questions,
        )

    metric_names = results[0].quality_scores.keys()
    quality_scores = {
        name: sum(r.quality_scores[name] for r in results) / request_count
        for name in metric_names
    }
    metrics = {
        "cost_per_request": total_cost / request_count,
        "total_cost": total_cost,
        "avg_input_tokens": sum(r.input_tokens for r in results) / request_count,
        "avg_output_tokens": sum(r.output_tokens for r in results) / request_count,
        "avg_latency_ms": sum(r.latency_ms for r in results) / request_count,
        "quality_scores": quality_scores,
        "request_count": request_count,
        "failed_questions": failed_questions,
    }
    return _VariantOutcome(metrics=metrics, failed_questions=failed_questions)


async def run_experiment(
    db: Session,
    experiment: Experiment,
    _http_client: httpx.AsyncClient | None = None,
    _evaluator: Evaluator | None = None,
) -> ExperimentOutcome:
    """Execute both variants of `experiment` concurrently against the sample
    app over HTTP (see docs/adr/0004), score each answer with the Answer
    Correctness evaluator, persist one ExperimentRun per variant, and return
    the comparison. Per-item requests within a variant are also run
    concurrently (bounded by `_MAX_CONCURRENT_ITEMS`); a single item's
    failure never cancels the others - it is logged and recorded in
    `failed_questions` (also persisted into that variant's `ExperimentRun.metrics`).

    Never raises for per-item failures; only raises if the dataset itself
    has no items. If every item in a variant fails, the experiment is marked
    `failed` (with `experiment.error` set) and the comparison fields on the
    returned `ExperimentOutcome` are `None` - they are deliberately never
    computed against a meaningless all-zero/all-failed baseline. Callers
    must check `experiment.status` before trusting the comparison fields.
    """
    evaluator = _evaluator or _resolve_evaluator(experiment)
    items = (
        db.query(EvaluationItem)
        .filter(EvaluationItem.dataset_id == experiment.evaluation_dataset_id)
        .all()
    )

    experiment.status = "running"
    linked_recommendation = _get_linked_recommendation(db, experiment)
    _advance_recommendation_lifecycle(db, linked_recommendation, "experiment_running")
    db.commit()

    if not items:
        experiment.status = "failed"
        experiment.error = "evaluation dataset has no items"
        db.commit()
        raise ValueError(experiment.error)

    owns_client = _http_client is None
    # 120s (not 60s): a real run showed the sample app's own downstream
    # generation (plus any tool-calling loop) can legitimately take
    # 30s+, and our own transient-error retries add further latency on
    # top of that - 60s was tight enough to produce client-side timeouts
    # that then got (correctly) retried, adding even more time.
    client = _http_client or httpx.AsyncClient(base_url=settings.sample_rag_app_url, timeout=120.0)
    try:
        baseline_outcome, experiment_outcome = await asyncio.gather(
            _run_variant(client, evaluator, items, experiment.baseline_config),
            _run_variant(client, evaluator, items, experiment.experiment_config),
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

    variant_fully_failed = (
        baseline_outcome.metrics["request_count"] == 0
        or experiment_outcome.metrics["request_count"] == 0
    )
    if variant_fully_failed:
        experiment.status = "failed"
        experiment.error = "all evaluation items failed for a variant: " + "; ".join(all_failures)
    else:
        experiment.status = "completed"
        # Clear any stale error from a previous failed attempt at this same
        # experiment (e.g. a transient rate limit that a retry/re-run
        # cleared up) - a completed experiment must never carry a leftover
        # error message, discovered for real when re-running a previously
        # failed experiment and seeing its old error text survive success.
        experiment.error = None

    db.commit()
    db.refresh(baseline_row)
    db.refresh(experiment_row)
    db.refresh(experiment)

    # Only compute the comparison when both variants actually produced data -
    # percentages derived against an all-zero/all-failed variant (e.g. "100%
    # cost reduction" for a run that produced no real data) are meaningless,
    # so we don't compute them at all in that case, not merely hide them.
    if variant_fully_failed:
        return ExperimentOutcome(
            experiment=experiment,
            baseline_run=baseline_row,
            experiment_run=experiment_row,
            cost_reduction_pct=None,
            quality_differences=None,
            latency_difference_ms=None,
            token_reduction_pct=None,
            failed_questions=all_failures,
        )

    comparison = compare_runs(baseline_row, experiment_row)
    # "validated" requires EVERY declared metric to individually clear the
    # threshold - a single cherry-picked metric passing must never hide a
    # regression on another metric the experiment explicitly measured.
    if comparison["quality_differences"] and all(
        diff >= QUALITY_VALIDATION_THRESHOLD for diff in comparison["quality_differences"].values()
    ):
        _advance_recommendation_lifecycle(db, linked_recommendation, "validated")
        db.commit()
    return ExperimentOutcome(
        experiment=experiment,
        baseline_run=baseline_row,
        experiment_run=experiment_row,
        cost_reduction_pct=comparison["cost_reduction_pct"],
        quality_differences=comparison["quality_differences"],
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

    baseline_quality: dict[str, float] = baseline.get("quality_scores") or {}
    experiment_quality: dict[str, float] = experiment.get("quality_scores") or {}
    quality_differences = {
        name: float(experiment_quality[name]) - float(baseline_quality[name])
        for name in baseline_quality
        if name in experiment_quality
    }
    latency_difference_ms = float(experiment["avg_latency_ms"]) - float(baseline["avg_latency_ms"])

    return {
        "cost_reduction_pct": cost_reduction_pct,
        "quality_differences": quality_differences,
        "latency_difference_ms": latency_difference_ms,
        "token_reduction_pct": token_reduction_pct,
    }

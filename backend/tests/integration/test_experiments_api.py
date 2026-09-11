import asyncio
import time
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.evaluation.base import Evaluator
from app.models.experiment import ExperimentRun
from app.models.optimization import OptimizationRecommendation
from app.services import experiments as experiments_service


def _create_project(client: TestClient, slug: str = "exp-project") -> dict:
    response = client.post("/projects", json={"name": "Exp Project", "slug": slug})
    assert response.status_code == 201
    return response.json()


def _import_dataset(client: TestClient, project_id: str) -> dict:
    response = client.post(
        f"/projects/{project_id}/evaluations/import",
        json={
            "name": "smoke-test-dataset",
            "description": "Two items for a fast integration test.",
            "items": [
                {
                    "question": "Why isn't Mercury the hottest planet?",
                    "expected_answer": "It has almost no atmosphere to trap heat.",
                    "source_doc": "01-mercury.txt",
                },
                {
                    "question": "What causes Venus's extreme surface temperature?",
                    "expected_answer": "A runaway greenhouse effect.",
                    "source_doc": "02-venus.txt",
                },
            ],
        },
    )
    assert response.status_code == 201
    return response.json()


def _import_dataset_with_items(client: TestClient, project_id: str, count: int) -> dict:
    items = [
        {
            "question": f"question {i}?",
            "expected_answer": f"answer {i}",
            "source_doc": f"{i:02d}-doc.txt",
        }
        for i in range(count)
    ]
    response = client.post(
        f"/projects/{project_id}/evaluations/import",
        json={"name": f"dataset-{count}-items", "items": items},
    )
    assert response.status_code == 201
    return response.json()["dataset"]


class _FakeChatResponse:
    def __init__(self, body: dict) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._body


class _FakeChatClient:
    """Stands in for the httpx.AsyncClient the experiment runner uses to
    call the sample app's /api/chat, so the test suite doesn't require the
    live Docker stack. See CLAUDE.md Phase 5 section 8 - a real end-to-end
    run against the live stack is done separately and reported outside
    pytest."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    async def post(self, url: str, json: dict) -> _FakeChatResponse:
        return _FakeChatResponse(
            {
                "response": "A plausible generated answer.",
                "usage": {"prompt_tokens": 500, "completion_tokens": 80, "total_tokens": 580},
            }
        )

    async def aclose(self) -> None:
        pass


class _FakeEvaluator(Evaluator):
    async def evaluate(self, question: str, expected_answer: str, actual_answer: str) -> float:
        return 0.8


@pytest.fixture()
def mock_experiment_infra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(experiments_service.httpx, "AsyncClient", _FakeChatClient)
    monkeypatch.setattr(experiments_service, "AnswerCorrectnessEvaluator", lambda: _FakeEvaluator())


def test_create_run_and_compare_experiment(
    client: TestClient, db_session: Session, mock_experiment_infra: None
) -> None:
    project = _create_project(client)
    dataset = _import_dataset(client, project["id"])["dataset"]

    create_response = client.post(
        f"/projects/{project['id']}/experiments",
        json={
            "name": "reduce top_k",
            "baseline_config": {},
            "experiment_config": {"top_k": 3},
            "evaluation_dataset_id": dataset["id"],
        },
    )
    assert create_response.status_code == 201
    experiment = create_response.json()
    assert experiment["status"] == "pending"

    run_response = client.post(f"/projects/{project['id']}/experiments/{experiment['id']}/run")
    assert run_response.status_code == 200
    comparison = run_response.json()

    assert comparison["experiment"]["status"] == "completed"
    assert comparison["baseline_run"]["metrics"]["request_count"] == 2
    assert comparison["experiment_run"]["metrics"]["request_count"] == 2
    assert comparison["failed_questions"] == []
    # Same fake response/config on both variants -> no real cost/quality delta.
    assert comparison["cost_reduction_pct"] == 0.0
    assert comparison["quality_difference"] == 0.0

    get_response = client.get(f"/projects/{project['id']}/experiments/{experiment['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "completed"

    list_response = client.get(f"/projects/{project['id']}/experiments")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_experiment_run_survives_dataset_with_no_items(
    client: TestClient, db_session: Session, mock_experiment_infra: None
) -> None:
    project = _create_project(client, slug="empty-dataset-project")
    empty_dataset = client.post(
        f"/projects/{project['id']}/evaluations/import",
        json={"name": "empty", "items": []},
    ).json()["dataset"]

    create_response = client.post(
        f"/projects/{project['id']}/experiments",
        json={
            "name": "no items",
            "baseline_config": {},
            "experiment_config": {},
            "evaluation_dataset_id": empty_dataset["id"],
        },
    )
    experiment_id = create_response.json()["id"]

    run_response = client.post(f"/projects/{project['id']}/experiments/{experiment_id}/run")
    assert run_response.status_code == 422


def test_adopt_requires_completed_experiment(
    client: TestClient, db_session: Session, mock_experiment_infra: None
) -> None:
    project = _create_project(client, slug="adopt-project")
    project_uuid = uuid.UUID(project["id"])

    recommendation = OptimizationRecommendation(
        project_id=project_uuid,
        workflow="rag-workflow",
        rule_name="excessive_retrieval_context",
        reason="test reason",
        current_config={"top_k": 8},
        proposed_config={"top_k": 5},
        estimated_cost_impact="~10% reduction",
        required_experiment={"description": "compare top_k 8 vs 5"},
        confidence=0.7,
    )
    db_session.add(recommendation)
    db_session.commit()
    db_session.refresh(recommendation)

    # No linked experiment yet -> adopting is rejected.
    adopt_response = client.patch(
        f"/projects/{project['id']}/optimizations/{recommendation.id}",
        json={"status": "adopted"},
    )
    assert adopt_response.status_code == 409

    # Rejecting is allowed at any time.
    reject_response = client.patch(
        f"/projects/{project['id']}/optimizations/{recommendation.id}",
        json={"status": "rejected"},
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "rejected"


def test_adopt_succeeds_once_linked_experiment_completes(
    client: TestClient, db_session: Session, mock_experiment_infra: None
) -> None:
    project = _create_project(client, slug="adopt-success-project")
    dataset = _import_dataset(client, project["id"])["dataset"]
    project_uuid = uuid.UUID(project["id"])

    recommendation = OptimizationRecommendation(
        project_id=project_uuid,
        workflow="rag-workflow",
        rule_name="excessive_retrieval_context",
        reason="test reason",
        current_config={"top_k": 8},
        proposed_config={"top_k": 5},
        estimated_cost_impact="~10% reduction",
        required_experiment={"description": "compare top_k 8 vs 5"},
        confidence=0.7,
    )
    db_session.add(recommendation)
    db_session.commit()
    db_session.refresh(recommendation)

    experiment_response = client.post(
        f"/projects/{project['id']}/experiments",
        json={
            "recommendation_id": str(recommendation.id),
            "name": "reduce top_k",
            "baseline_config": {"top_k": 8},
            "experiment_config": {"top_k": 5},
            "evaluation_dataset_id": dataset["id"],
        },
    )
    assert experiment_response.status_code == 201
    experiment_id = experiment_response.json()["id"]

    run_response = client.post(f"/projects/{project['id']}/experiments/{experiment_id}/run")
    assert run_response.status_code == 200

    adopt_response = client.patch(
        f"/projects/{project['id']}/optimizations/{recommendation.id}",
        json={"status": "adopted"},
    )
    assert adopt_response.status_code == 200
    assert adopt_response.json()["status"] == "adopted"
    assert adopt_response.json()["experiment_id"] == experiment_id


class _FakeVariantFailingClient:
    """Every request whose `config_override.model` is `_FAILING_MODEL` fails
    with an HTTP error; everything else succeeds like `_FakeChatClient`. Lets
    a test force one whole variant to fail without touching real infra."""

    FAILING_MODEL = "nonexistent-model"

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    async def post(self, url: str, json: dict) -> _FakeChatResponse:
        config_override = json.get("config_override") or {}
        if config_override.get("model") == self.FAILING_MODEL:
            request = httpx.Request("POST", "http://sample-rag-app/api/chat")
            raise httpx.ConnectError("no such model", request=request)
        return _FakeChatResponse(
            {
                "response": "A plausible generated answer.",
                "usage": {"prompt_tokens": 500, "completion_tokens": 80, "total_tokens": 580},
            }
        )

    async def aclose(self) -> None:
        pass


def test_run_returns_error_when_a_variant_fully_fails(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When every item in a variant fails, the run endpoint must surface a
    clear error instead of a 200 with fabricated comparison percentages, and
    `compare_runs` must never be invoked with a request_count == 0 variant."""
    monkeypatch.setattr(experiments_service.httpx, "AsyncClient", _FakeVariantFailingClient)
    monkeypatch.setattr(experiments_service, "AnswerCorrectnessEvaluator", lambda: _FakeEvaluator())

    called_compare_runs = False
    original_compare_runs = experiments_service.compare_runs

    def _spy_compare_runs(*args: object, **kwargs: object) -> dict:
        nonlocal called_compare_runs
        called_compare_runs = True
        return original_compare_runs(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(experiments_service, "compare_runs", _spy_compare_runs)

    project = _create_project(client, slug="full-failure-project")
    dataset = _import_dataset(client, project["id"])["dataset"]

    create_response = client.post(
        f"/projects/{project['id']}/experiments",
        json={
            "name": "broken model swap",
            "baseline_config": {},
            "experiment_config": {"model": _FakeVariantFailingClient.FAILING_MODEL},
            "evaluation_dataset_id": dataset["id"],
        },
    )
    assert create_response.status_code == 201
    experiment_id = create_response.json()["id"]

    run_response = client.post(f"/projects/{project['id']}/experiments/{experiment_id}/run")

    assert run_response.status_code in (422, 409)
    assert "detail" in run_response.json()
    assert not called_compare_runs

    get_response = client.get(f"/projects/{project['id']}/experiments/{experiment_id}")
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["status"] == "failed"
    assert body["error"]


def test_per_item_failure_is_persisted_in_run_metrics(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A single failing item (not a whole-variant failure) should still
    complete the experiment, but the failure must be recoverable afterwards
    from the persisted ExperimentRun.metrics - not just the transient
    response from the /run call."""

    failing_question = "question 1?"

    class _FakePartiallyFailingClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def post(self, url: str, json: dict) -> _FakeChatResponse:
            question = json["messages"][0]["content"]
            if question == failing_question:
                request = httpx.Request("POST", "http://sample-rag-app/api/chat")
                raise httpx.ReadTimeout("timed out", request=request)
            return _FakeChatResponse(
                {
                    "response": "A plausible generated answer.",
                    "usage": {"prompt_tokens": 500, "completion_tokens": 80, "total_tokens": 580},
                }
            )

        async def aclose(self) -> None:
            pass

    monkeypatch.setattr(experiments_service.httpx, "AsyncClient", _FakePartiallyFailingClient)
    monkeypatch.setattr(experiments_service, "AnswerCorrectnessEvaluator", lambda: _FakeEvaluator())

    project = _create_project(client, slug="partial-failure-project")
    dataset = _import_dataset_with_items(client, project["id"], count=3)

    create_response = client.post(
        f"/projects/{project['id']}/experiments",
        json={
            "name": "partial failure",
            "baseline_config": {},
            "experiment_config": {"top_k": 3},
            "evaluation_dataset_id": dataset["id"],
        },
    )
    experiment_id = create_response.json()["id"]

    run_response = client.post(f"/projects/{project['id']}/experiments/{experiment_id}/run")
    assert run_response.status_code == 200
    body = run_response.json()
    assert body["experiment"]["status"] == "completed"
    assert any(failing_question in q for q in body["failed_questions"])

    # The important assertion: re-fetch the persisted rows from the DB in a
    # *fresh* query, independent of the transient /run response, and confirm
    # the failure is queryable there too.
    runs = (
        db_session.query(ExperimentRun)
        .filter(ExperimentRun.experiment_id == uuid.UUID(experiment_id))
        .all()
    )
    assert len(runs) == 2
    for run in runs:
        assert run.metrics["request_count"] == 2
        assert any(failing_question in q for q in run.metrics["failed_questions"])


def test_concurrent_item_execution_produces_correct_aggregated_metrics(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Items within a variant (and the two variants themselves) should run
    concurrently rather than strictly sequentially. We assert correctness of
    the aggregated metrics (the robust check) and, as a rough sanity check,
    that wall-clock time is meaningfully less than fully sequential
    execution would take."""

    item_count = 5
    delay_seconds = 0.05

    class _FakeSlowClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def post(self, url: str, json: dict) -> _FakeChatResponse:
            await asyncio.sleep(delay_seconds)
            return _FakeChatResponse(
                {
                    "response": "A plausible generated answer.",
                    "usage": {"prompt_tokens": 500, "completion_tokens": 80, "total_tokens": 580},
                }
            )

        async def aclose(self) -> None:
            pass

    monkeypatch.setattr(experiments_service.httpx, "AsyncClient", _FakeSlowClient)
    monkeypatch.setattr(experiments_service, "AnswerCorrectnessEvaluator", lambda: _FakeEvaluator())

    project = _create_project(client, slug="concurrency-project")
    dataset = _import_dataset_with_items(client, project["id"], count=item_count)

    create_response = client.post(
        f"/projects/{project['id']}/experiments",
        json={
            "name": "concurrency check",
            "baseline_config": {},
            "experiment_config": {"top_k": 3},
            "evaluation_dataset_id": dataset["id"],
        },
    )
    experiment_id = create_response.json()["id"]

    fully_sequential_seconds = item_count * 2 * delay_seconds

    start = time.perf_counter()
    run_response = client.post(f"/projects/{project['id']}/experiments/{experiment_id}/run")
    elapsed_seconds = time.perf_counter() - start

    assert run_response.status_code == 200
    body = run_response.json()
    assert body["failed_questions"] == []
    assert body["baseline_run"]["metrics"]["request_count"] == item_count
    assert body["experiment_run"]["metrics"]["request_count"] == item_count
    assert body["cost_reduction_pct"] == 0.0

    # Rough sanity check only (correctness above is the real assertion):
    # concurrent execution should be meaningfully faster than the fully
    # sequential worst case.
    assert elapsed_seconds < fully_sequential_seconds * 0.6


@pytest.mark.parametrize(
    "status_code",
    [
        429,
        # The real-world case: the sample app doesn't propagate the
        # underlying provider's 429 as a 429 - an unhandled
        # openai.RateLimitError inside its own request handler surfaces to
        # us as a plain 500 via its default FastAPI exception handler. This
        # is exactly what happened for real under _MAX_CONCURRENT_ITEMS
        # concurrency against z.ai's free glm-4.5-flash tier.
        500,
    ],
)
def test_transient_rate_limit_is_retried_not_treated_as_a_failure(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch, status_code: int
) -> None:
    """A transient 429/5xx from the sample app is retried rather than
    counted as a permanent item failure - see the _RATE_LIMIT_* constants in
    app.services.experiments."""

    # Avoid real sleeping in the test - the retry backoff would otherwise
    # add several real seconds per retried item.
    async def _no_sleep(seconds: float) -> None:
        pass

    monkeypatch.setattr(experiments_service.asyncio, "sleep", _no_sleep)

    class _FakeTransientlyFailingOnceClient:
        """The first call for each question fails transiently; the retry succeeds."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            self._seen_questions: set[str] = set()

        async def post(self, url: str, json: dict) -> _FakeChatResponse:
            question = json["messages"][0]["content"]
            if question not in self._seen_questions:
                self._seen_questions.add(question)
                request = httpx.Request("POST", "http://sample-rag-app/api/chat")
                response = httpx.Response(
                    status_code,
                    json={"error": {"message": "transient error"}},
                    request=request,
                )
                raise httpx.HTTPStatusError("transient error", request=request, response=response)
            return _FakeChatResponse(
                {
                    "response": "A plausible generated answer.",
                    "usage": {"prompt_tokens": 500, "completion_tokens": 80, "total_tokens": 580},
                }
            )

        async def aclose(self) -> None:
            pass

    monkeypatch.setattr(experiments_service.httpx, "AsyncClient", _FakeTransientlyFailingOnceClient)
    monkeypatch.setattr(experiments_service, "AnswerCorrectnessEvaluator", lambda: _FakeEvaluator())

    project = _create_project(client, slug=f"rate-limit-retry-project-{status_code}")
    dataset = _import_dataset(client, project["id"])["dataset"]

    create_response = client.post(
        f"/projects/{project['id']}/experiments",
        json={
            "name": "rate limit retry",
            "baseline_config": {},
            "experiment_config": {"top_k": 4},
            "evaluation_dataset_id": dataset["id"],
        },
    )
    experiment_id = create_response.json()["id"]

    run_response = client.post(f"/projects/{project['id']}/experiments/{experiment_id}/run")

    assert run_response.status_code == 200
    body = run_response.json()
    assert body["failed_questions"] == []
    assert body["baseline_run"]["metrics"]["request_count"] == 2
    assert body["experiment_run"]["metrics"]["request_count"] == 2


def test_stale_error_is_cleared_after_a_successful_retry(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Discovered for real: re-running a previously failed experiment (e.g.
    after a transient rate limit clears up) must not leave the old failure's
    `error` text on a now-`completed` experiment."""
    monkeypatch.setattr(experiments_service.httpx, "AsyncClient", _FakeVariantFailingClient)
    monkeypatch.setattr(experiments_service, "AnswerCorrectnessEvaluator", lambda: _FakeEvaluator())

    project = _create_project(client, slug="stale-error-project")
    dataset = _import_dataset(client, project["id"])["dataset"]

    create_response = client.post(
        f"/projects/{project['id']}/experiments",
        json={
            "name": "flaky then fixed",
            "baseline_config": {},
            "experiment_config": {"model": _FakeVariantFailingClient.FAILING_MODEL},
            "evaluation_dataset_id": dataset["id"],
        },
    )
    experiment_id = create_response.json()["id"]

    first_run = client.post(f"/projects/{project['id']}/experiments/{experiment_id}/run")
    assert first_run.status_code in (422, 409)
    failed_body = client.get(f"/projects/{project['id']}/experiments/{experiment_id}").json()
    assert failed_body["status"] == "failed"
    assert failed_body["error"]

    # The underlying problem clears up (here: simulated by swapping back to
    # a working client) and the same experiment is retried.
    monkeypatch.setattr(experiments_service.httpx, "AsyncClient", _FakeChatClient)
    second_run = client.post(f"/projects/{project['id']}/experiments/{experiment_id}/run")
    assert second_run.status_code == 200

    completed_body = client.get(f"/projects/{project['id']}/experiments/{experiment_id}").json()
    assert completed_body["status"] == "completed"
    assert completed_body["error"] is None

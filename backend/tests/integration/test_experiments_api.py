import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.evaluation.base import Evaluator
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

import pytest

from app.evaluation import AnswerCorrectnessEvaluator
from app.models.experiment import Experiment
from app.services.experiments import _resolve_evaluator


def _experiment(evaluator_type: str, evaluator_metrics: list[str] | None) -> Experiment:
    return Experiment(
        project_id=None,  # type: ignore[arg-type]
        name="test",
        baseline_config={},
        experiment_config={},
        evaluation_dataset_id=None,  # type: ignore[arg-type]
        evaluator_type=evaluator_type,
        evaluator_metrics=evaluator_metrics,
    )


def test_fallback_evaluator_type_resolves_to_answer_correctness() -> None:
    evaluator = _resolve_evaluator(_experiment("fallback", None))
    assert isinstance(evaluator, AnswerCorrectnessEvaluator)


def test_deepeval_evaluator_type_without_metrics_raises() -> None:
    with pytest.raises(ValueError, match="evaluator_metrics"):
        _resolve_evaluator(_experiment("deepeval", None))


def test_deepeval_evaluator_type_without_package_installed_raises_import_error() -> None:
    # deepeval isn't installed in this test venv (it's an optional extra) -
    # resolving a deepeval-type experiment must surface that clearly.
    with pytest.raises(ImportError, match="deepeval"):
        _resolve_evaluator(_experiment("deepeval", ["faithfulness"]))

import pytest

from app.evaluation.deepeval_evaluator import DeepEvalEvaluator


def test_raises_actionable_import_error_when_deepeval_not_installed() -> None:
    """deepeval is an optional extra (not installed in this test venv) - see
    sdk/backend pyproject.toml - so instantiating without it must fail
    immediately with a clear message, not deep inside evaluate()."""
    with pytest.raises(ImportError, match="deepeval"):
        DeepEvalEvaluator(["faithfulness"])

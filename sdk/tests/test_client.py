import pytest

from ai_cost_optimizer.client import OptimizerClient
from ai_cost_optimizer.config import ExperimentConfig

ENV_VARS = [
    "AI_OPTIMIZER_MODEL",
    "AI_OPTIMIZER_TOP_K",
    "AI_OPTIMIZER_PROMPT",
    "AI_OPTIMIZER_MAX_TOKENS",
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_get_config_defaults_to_all_none_when_no_env_vars_set() -> None:
    config = OptimizerClient(project_slug="sample-rag-app").get_config()

    assert config == ExperimentConfig(model=None, top_k=None, prompt=None, max_tokens=None)


def test_get_config_reads_values_from_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_OPTIMIZER_MODEL", "glm-4-flash")
    monkeypatch.setenv("AI_OPTIMIZER_TOP_K", "2")
    monkeypatch.setenv("AI_OPTIMIZER_PROMPT", "Be terse.")
    monkeypatch.setenv("AI_OPTIMIZER_MAX_TOKENS", "256")

    config = OptimizerClient(project_slug="sample-rag-app").get_config()

    assert config == ExperimentConfig(
        model="glm-4-flash", top_k=2, prompt="Be terse.", max_tokens=256
    )


def test_get_config_treats_empty_string_env_vars_as_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_OPTIMIZER_MODEL", "")
    monkeypatch.setenv("AI_OPTIMIZER_TOP_K", "")

    config = OptimizerClient(project_slug="sample-rag-app").get_config()

    assert config.model is None
    assert config.top_k is None

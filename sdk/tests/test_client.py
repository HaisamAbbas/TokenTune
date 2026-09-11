import pytest

from tokentune.client import OptimizerClient
from tokentune.config import ExperimentConfig

ENV_VARS = [
    "TOKENTUNE_MODEL",
    "TOKENTUNE_TOP_K",
    "TOKENTUNE_PROMPT",
    "TOKENTUNE_MAX_TOKENS",
    "TOKENTUNE_BACKEND_URL",
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_get_config_defaults_to_all_none_when_no_env_vars_set() -> None:
    config = OptimizerClient(project_slug="sample-rag-app").get_config()

    assert config == ExperimentConfig(model=None, top_k=None, prompt=None, max_tokens=None)


def test_get_config_reads_values_from_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOKENTUNE_MODEL", "glm-4-flash")
    monkeypatch.setenv("TOKENTUNE_TOP_K", "2")
    monkeypatch.setenv("TOKENTUNE_PROMPT", "Be terse.")
    monkeypatch.setenv("TOKENTUNE_MAX_TOKENS", "256")

    config = OptimizerClient(project_slug="sample-rag-app").get_config()

    assert config == ExperimentConfig(
        model="glm-4-flash", top_k=2, prompt="Be terse.", max_tokens=256
    )


def test_get_config_treats_empty_string_env_vars_as_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TOKENTUNE_MODEL", "")
    monkeypatch.setenv("TOKENTUNE_TOP_K", "")

    config = OptimizerClient(project_slug="sample-rag-app").get_config()

    assert config.model is None
    assert config.top_k is None

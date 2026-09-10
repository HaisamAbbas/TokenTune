import os

from ai_cost_optimizer.config import ExperimentConfig

# V1 scoping decision: get_config() reads its values from local environment
# variables rather than fetching from a live backend API. This is a real
# simplification, not the intended end state: `project_slug`/`environment`
# are accepted here for forward compatibility with a future call that looks
# up an experiment-assigned config from the platform backend, but today they
# are unused. A field left unset (None) means "use the calling app's own
# default" — it does NOT mean "ask the platform for the production value".
_ENV_PREFIX = "AI_OPTIMIZER_"


class OptimizerClient:
    """Entry point an AI application uses to connect to the platform.

    V1 skeleton: identifies the project/environment and returns the
    production configuration. Experiment variant resolution and telemetry
    reporting are added in later phases.
    """

    def __init__(self, project_slug: str, environment: str = "production") -> None:
        self.project_slug = project_slug
        self.environment = environment

    def get_config(self) -> ExperimentConfig:
        """Return the config an app should apply for this project/environment.

        See the module-level comment: V1 reads this from environment
        variables (`AI_OPTIMIZER_MODEL`, `AI_OPTIMIZER_TOP_K`,
        `AI_OPTIMIZER_PROMPT`, `AI_OPTIMIZER_MAX_TOKENS`), not from a live
        backend call. Unset variables map to `None` fields, which callers
        should treat as "no override" rather than "fetch failed".
        """
        return ExperimentConfig(
            model=os.environ.get(f"{_ENV_PREFIX}MODEL") or None,
            top_k=_int_or_none(os.environ.get(f"{_ENV_PREFIX}TOP_K")),
            prompt=os.environ.get(f"{_ENV_PREFIX}PROMPT") or None,
            max_tokens=_int_or_none(os.environ.get(f"{_ENV_PREFIX}MAX_TOKENS")),
        )


def _int_or_none(value: str | None) -> int | None:
    return int(value) if value else None

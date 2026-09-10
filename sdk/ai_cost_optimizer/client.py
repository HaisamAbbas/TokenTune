from ai_cost_optimizer.config import ExperimentConfig


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
        return ExperimentConfig()

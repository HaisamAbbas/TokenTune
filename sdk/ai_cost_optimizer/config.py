from pydantic import BaseModel


class ExperimentConfig(BaseModel):
    """Optimizable parameters an application can request from the platform.

    Only the V1-supported parameters are modeled: model, top_k, prompt, max_tokens.
    """

    model: str | None = None
    top_k: int | None = None
    prompt: str | None = None
    max_tokens: int | None = None

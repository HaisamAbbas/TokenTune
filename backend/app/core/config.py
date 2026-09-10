from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dev.db"

    # Phase 5: the litellm-proxy service (see docker-compose.yml) fronting
    # the GLM models, used by AnswerCorrectnessEvaluator as an LLM judge.
    # Default matches the Docker network's service name/port; override to
    # "http://localhost:4000" when running the backend outside Docker.
    litellm_base_url: str = "http://litellm-proxy:4000"
    litellm_api_key: str = "None"
    judge_model: str = "glm-4.5-flash"

    # Phase 5: the sample-rag-app service's /api/chat, used by the
    # experiment runner. Default matches the Docker network's service
    # name/port; override to "http://localhost:8001" when running the
    # backend outside Docker (see docker-compose.yml: sample-rag-app maps
    # container port 8000 to host port 8001).
    sample_rag_app_url: str = "http://sample-rag-app:8000"


settings = Settings()

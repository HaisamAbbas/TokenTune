# AI Cost Optimization Platform

An internal engineering platform that sits above existing LLM observability
(Langfuse) and turns telemetry into experimentally validated cost/quality
recommendations for AI applications (RAG systems, agents). It is not a
Langfuse clone, a token counter, or a billing dashboard — it answers: given
an application's telemetry, where can cost be reduced without materially
hurting quality, and can that be proven with a controlled experiment against
an evaluation dataset?

## Running locally

```bash
cp .env.example .env
docker compose up -d postgres
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Or bring up the whole stack (postgres + backend) with `docker compose up`.

Run the backend tests:

```bash
cd backend
uv run pytest
uv run ruff check .
uv run mypy app
```

## Project status: Phase 1 of 5

Implemented:
- Repository structure (`backend/`, `sdk/`, `examples/`)
- FastAPI backend skeleton (`/health`, `/projects`)
- PostgreSQL schema via SQLAlchemy + Alembic: `projects`, `environments`,
  `traces`, `llm_calls`
- Basic project model and basic telemetry model
- Bare `ai_cost_optimizer` SDK skeleton (`OptimizerClient.get_config()`)
- Unit + integration tests, ruff, mypy

Not yet implemented (later phases):
- Langfuse adapter and telemetry ingestion (Phase 2)
- Cost aggregation and cost dashboard (Phase 2)
- Optimization rule engine and recommendation model (Phase 3)
- Evaluation dataset abstraction and experiment execution (Phase 4)
- Experiment comparison, adopt/reject workflow (Phase 5)
- Next.js dashboard
- Forked sample RAG app (`examples/sample-rag-app/`, based on
  [ajac-zero/example-rag-app](https://github.com/ajac-zero/example-rag-app))

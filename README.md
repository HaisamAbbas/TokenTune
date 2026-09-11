# AI Cost Optimization Platform

An internal engineering platform that sits above existing LLM observability
(Langfuse) and turns telemetry into experimentally validated cost/quality
recommendations for AI applications (RAG systems, agents). It is not a
Langfuse clone, a token counter, or a billing dashboard — it answers: given
an application's telemetry, where can cost be reduced without materially
hurting quality, and can that be proven with a controlled experiment against
an evaluation dataset?

The full loop, end to end: **Observe** (Langfuse telemetry → normalized
events) → **Analyze** (cost aggregation) → **Detect** (rule engine flags an
optimization opportunity) → **Experiment** (run baseline vs. an alternative
config against an evaluation dataset, in complete isolation from production)
→ **Compare** (real cost/quality/latency deltas) → **Recommend** (adopt or
reject, backed by evidence). See `CONTEXT.md` for the domain glossary and
`docs/adr/` for the architectural decisions behind it.

## Running locally

The full stack (backend + Postgres + a real sample RAG app + its
dependencies) runs via Docker Compose:

```bash
cp .env.example .env
cp backend/.env.example backend/.env   # add your own LLM provider key (see below)
docker compose up -d
docker compose run --rm sample-rag-app python scripts/ingest.py
```

This brings up:
- `postgres` — the platform's own database
- `backend` — the FastAPI platform API (this repo's core)
- `qdrant` — vector store for the sample RAG app
- `tei` — self-hosted BGE-M3 embeddings (HuggingFace Text Embeddings Inference)
- `litellm-proxy` — routes chat completions to your configured LLM provider
  and (optionally) logs to Langfuse
- `sample-rag-app` — a forked, real agentic RAG app
  ([ajac-zero/example-rag-app](https://github.com/ajac-zero/example-rag-app),
  MIT) used to prove the platform end-to-end; see
  `examples/sample-rag-app/README.md`

To run just the backend against a local Postgres, without the sample app:

```bash
docker compose up -d postgres
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Run the backend tests:

```bash
cd backend
uv run pytest
uv run ruff check .
uv run mypy app
```

## API surface

All routes are under `/projects`:

```
POST   /projects                                       create a project
GET    /projects                                       list projects
GET    /projects/{id}                                  get a project

POST   /projects/{id}/telemetry/import                 pull + normalize Langfuse telemetry
GET    /projects/{id}/cost                              aggregated cost/tokens/latency (group_by day|model|workflow)

POST   /projects/{id}/optimizations/analyze             run the rule engine, create recommendations
GET    /projects/{id}/optimizations                     list recommendations
PATCH  /projects/{id}/optimizations/{recommendation_id}  adopt or reject a recommendation

POST   /projects/{id}/evaluations/import                import an evaluation dataset (question/answer pairs)
GET    /projects/{id}/evaluations                       list evaluation datasets

POST   /projects/{id}/experiments                       create an experiment (baseline vs. alternative config)
POST   /projects/{id}/experiments/{id}/run               run it against an evaluation dataset, returns the comparison
GET    /projects/{id}/experiments                       list experiments
GET    /projects/{id}/experiments/{id}                   get one, including its persisted run metrics
```

## Project status: complete (Phases 1–5)

- **Phase 1** — repo structure, FastAPI skeleton, Postgres schema (`projects`,
  `environments`, `traces`, `llm_calls`), bare SDK skeleton.
- **Phase 2** — Langfuse adapter (v2 observations API), pricing fallback,
  telemetry ingestion, cost aggregation.
- **Phase 3** — rule engine (Rules A–D: excessive retrieval context, model
  cost, prompt size, unnecessary generation calls), `OptimizationRecommendation`s.
- **Phase 4** — real sample RAG app forked in and running (agentic RAG,
  Docker: Qdrant + BGE-M3/TEI + LiteLLM proxy), SDK config-swap mechanism
  (`optimizer.get_config()`, per-request override), `RetrievalStep` +
  Langfuse `retriever` telemetry mapping, a real evaluation dataset.
- **Phase 5** — `Experiment`/`ExperimentRun`/`EvaluationDataset` models,
  experiment execution over HTTP against the sample app (concurrent, bounded;
  see `docs/adr/0004`), an Answer Correctness LLM-judge evaluator, real
  cost/quality/latency/token comparison, and the adopt/reject workflow
  (gated on a completed experiment).
- **Phase 6** — `dashboard/`, a Next.js (App Router, TypeScript) frontend over
  the full API surface above: project overview (KPI strip + cost-over-time
  chart + recent recommendations), a fuller cost breakdown view, the
  optimizations list (filter/run-analysis/reject/create-experiment), the
  experiment comparison view (run/adopt/reject), and evaluation dataset
  import — restyled shadcn/ui + Tailwind + Recharts against an approved
  design (oklch light/dark tokens, pill buttons, status-dot pattern).

Not yet built, out of scope for V1 per the original spec:
- Additional evaluators (faithfulness, context relevance) — the evaluation
  abstraction supports adding them, only Answer Correctness is implemented
- Live Langfuse instance integration (built and tested against the real API
  shape and real sample-app telemetry, but not yet run against a live account)

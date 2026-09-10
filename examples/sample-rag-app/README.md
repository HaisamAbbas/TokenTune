# Sample RAG App

A small, agentic RAG pipeline used as a real, running reference application for
this platform (Phase 4a). It is forked from
[`ajac-zero/example-rag-app`](https://github.com/ajac-zero/example-rag-app)
(MIT licensed, see `LICENSE`), with the following changes for this repo:

- **Split chat/embedding config** — `src/rag/config.py` now has independent
  `chat_url`/`chat_api_key` (for the LiteLLM proxy) and `embed_url`/`embed_api_key`
  (for the embedding service), instead of one shared `openai_url`/`openai_api_key`.
- **GLM via LiteLLM** — `litellm-config.yml` routes chat completions through
  LiteLLM's `zai/` provider to z.ai's GLM models: `glm-4.5-flash` (free tier,
  default), plus `glm-5.3-flash` and `glm-5.3` (paid, available for later
  cost-comparison experiments). Langfuse logging is optional and disabled by
  default (`success_callback: []`) since this phase has no live Langfuse
  instance; the proxy starts fine without Langfuse credentials.
- **BGE-M3 embeddings via TEI** — embeddings are served by HuggingFace's Text
  Embeddings Inference (TEI), serving `BAAI/bge-m3` through its
  OpenAI-compatible `/v1/embeddings` endpoint (note the `/v1` in `embed_url`,
  which TEI requires but the LiteLLM proxy does not).
- **Fixture corpus + ingestion script** — replaces the upstream Wikipedia/Docling
  ingestion notebook with `corpus/` (12 short hand-written documents about the
  Solar System) and `scripts/ingest.py`, a small script that embeds and upserts
  them into Qdrant. This keeps the demo fast instead of ingesting a large corpus.
- The `rag-ui/` React chat UI from the upstream repo was **not** forked in —
  this platform doesn't need a chat UI, only the RAG pipeline, and skipping it
  keeps this example backend-only and easier to run in CI/compose.

What was kept as-is from upstream: the agentic `Agent` (in
`src/rag/agent/__init__.py`) that lets the LLM decide whether to call
`hybrid_search`, `semantic_search`, or `keyword_search` against Qdrant; the
FastAPI (`/api/chat`, `/api/models`) and Typer CLI entrypoints; and the test
suite layout.

**Out of scope for this pass** (a separate, later pass): our SDK integration,
the experiment wrapper, and the Langfuse retrieval-step adapter mapping. This
is purely "get a real RAG app running end-to-end."

## Running it

From the repo root:

```bash
cp .env.example .env   # fill in ZAI_API_KEY at minimum
docker compose up qdrant tei litellm-proxy sample-rag-app
```

Then, in another terminal, ingest the fixture corpus:

```bash
docker compose run --rm sample-rag-app uv run python scripts/ingest.py
```

And query the agent:

```bash
curl -s http://localhost:8001/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"model": "glm-4.5-flash", "messages": [{"role": "user", "content": "What is Olympus Mons and which planet is it on?"}]}'
```

`GET http://localhost:8001/api/models` lists the models configured in
`litellm-config.yml`.

## Notes

- `qdrant` (6333/6334), `tei` (8080), and `litellm-proxy` (4000) are also
  exposed on the host for debugging.
- `scripts/ingest.py` recreates the Qdrant collection each run — safe to
  re-run any time you want to reset the fixture corpus.
- To try the paid GLM models, pass `"model": "glm-5.3-flash"` or
  `"model": "glm-5.3"` in the `/api/chat` request body instead.

Status: implemented (Phase 3) — model and migration exist; adapter population is Phase 4

# Model retrieval as an explicit Retrieval Step, not inferred from prompt size

Rule A ("excessive retrieval context") needs to reason about how much of a Workflow's cost comes from retrieval (top_k, chunk count, retrieved token count). We could infer this indirectly by diffing an LLM Call's actual prompt size against its template size, but that's guesswork and breaks the moment prompt templates change. Instead, retrieval will be captured as its own concept alongside LLM Call, populated by the same telemetry adapters whenever the source observability tool records a retrieval span. This costs an extra concept in the domain model, in exchange for recommendations that cite real retrieval numbers instead of estimates.

Phase 3 (commit `6b8497e`) added the `RetrievalStep` model and migration. Nothing populates it from real telemetry yet outside of tests: `LangfuseAdapter` does not map Langfuse's "retriever"-type observations into `RetrievalStep` rows (see the `# TODO: Phase 4` comment in `backend/app/models/telemetry.py`). That adapter mapping is deferred to Phase 4.

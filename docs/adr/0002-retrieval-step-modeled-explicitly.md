Status: implemented (Phase 3 model/migration; Phase 4 adapter mapping)

# Model retrieval as an explicit Retrieval Step, not inferred from prompt size

Rule A ("excessive retrieval context") needs to reason about how much of a Workflow's cost comes from retrieval (top_k, chunk count, retrieved token count). We could infer this indirectly by diffing an LLM Call's actual prompt size against its template size, but that's guesswork and breaks the moment prompt templates change. Instead, retrieval will be captured as its own concept alongside LLM Call, populated by the same telemetry adapters whenever the source observability tool records a retrieval span. This costs an extra concept in the domain model, in exchange for recommendations that cite real retrieval numbers instead of estimates.

Phase 3 (commit `6b8497e`) added the `RetrievalStep` model and migration; nothing populated it from real telemetry yet outside of tests.

Phase 4 closes that gap on both ends:
- `examples/sample-rag-app`'s `Agent` decorates its `_hybrid_search_pipeline`/`_semantic_search_pipeline`/`_keyword_search_pipeline` methods with Langfuse's `@observe(as_type="retriever")` and attaches the real `list[SearchResult]` as the observation's output (the methods themselves return a prompt-template string, so the raw results are attached explicitly via `langfuse.update_current_span(output=...)`).
- `LangfuseAdapter._normalize` now dispatches `type: "retriever"` observations (from Langfuse's v2 observations API, with the `io` field group added to the request) to `_normalize_retrieval`, producing a `NormalizedRetrievalEvent` (a sibling of `NormalizedTelemetryEvent`, not a subclass, since the two shapes share no meaningful fields). `top_k` comes from the retriever call's `limit` kwarg, `chunk_count` from the output list length, and `retrieved_tokens` from a whitespace-split estimate over each chunk's content (not a real tokenizer count).
- `app.services.ingestion.import_telemetry` persists `NormalizedRetrievalEvent`s as `RetrievalStep` rows (deduped by a new `RetrievalStep.span_id` column, mirroring `LLMCall.span_id`), alongside its existing `Trace`/`LLMCall` persistence.

See `backend/tests/unit/test_langfuse_adapter_retrieval.py` (against a hand-written fixture at `backend/tests/fixtures/langfuse_retriever_observation.json`, shaped after the real instrumentation above) and `backend/tests/integration/test_telemetry_api.py::test_import_telemetry_persists_retrieval_steps`.

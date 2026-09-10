Status: proposed — targeted for Phase 3, not yet implemented

# Model retrieval as an explicit Retrieval Step, not inferred from prompt size

Rule A ("excessive retrieval context") needs to reason about how much of a Workflow's cost comes from retrieval (top_k, chunk count, retrieved token count). We could infer this indirectly by diffing an LLM Call's actual prompt size against its template size, but that's guesswork and breaks the moment prompt templates change. Instead, retrieval will be captured as its own concept alongside LLM Call, populated by the same telemetry adapters whenever the source observability tool records a retrieval span. This costs an extra concept in the domain model, in exchange for recommendations that cite real retrieval numbers instead of estimates.

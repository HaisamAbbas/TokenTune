Status: ready-for-agent

# TokenTune SDK — v1 runtime cost/quality optimization spec

Finalized after a full grilling pass (23 questions across 4 rounds, all
answered by the user). This replaces the earlier brainstorm drafts in this
same file's history — the ideas from those drafts are preserved here only
where they survived grilling; superseded/deferred ideas are noted as such,
not silently dropped.

## Product framing

*"Can I replace this expensive AI configuration with a cheaper one without
meaningfully reducing the capability of my application?"*

**Architectural boundary:** DeepEval owns QUALITY. The platform's own
telemetry owns COST, LATENCY, TOKENS. The platform combines the two into a
comparison — it does not reimplement evaluation.

## Package rename

The SDK is renamed from `ai_cost_optimizer` to **`tokentune`**, matching the
product name. Clean rename, no backward-compat shim (pre-1.0, the only real
caller is `examples/sample-rag-app`, which gets updated in the same change).

## v1 scope (confirmed boundary — nothing more, nothing less)

v1 ships exactly:
1. **Telemetry reporting** — `client.report(...)` added to the existing
   `get_config()` flow.
2. **DeepEval as an optional evaluator** for quality scoring, alongside the
   existing `AnswerCorrectnessEvaluator` kept as the no-DeepEval fallback.
3. **Mode A (offline benchmark)** — run every candidate config against a
   dataset, compare cost/quality/latency, done. The developer reads the
   comparison table and decides manually.

**Explicitly deferred, not partially started, in v1:**
- §4 configurable-variable generalization (RAG/agent knobs beyond model)
  and parameter sweeps
- §5 tool-call/retry data capture
- §6 the Decision Engine (constraint-based recommendation)
- §7 the `@optimize` decorator and framework adapters (LangChain/LlamaIndex/
  OpenAI-SDK-compatible) — these are Mode B (live traffic) concerns; v1 has
  no live-traffic code path for them to wrap
- Mode B itself (shadow mode, traffic-split/canary ramp)

Design decisions for the deferred pieces are captured below so the *next*
slice isn't re-litigated from scratch, but none of it is built now.

## 1. DeepEval integration (v1)

- **Dependency type**: optional extra (`pip install tokentune[deepeval]`),
  not a hard dependency. `AnswerCorrectnessEvaluator` remains the fallback
  for projects without DeepEval installed — retiring it would make DeepEval
  a de facto hard requirement.
- **Evaluator selection is per-experiment**, not a project-level toggle. One
  project can have some experiments using DeepEval metrics and others using
  the fallback evaluator.
- **Verified DeepEval facts** (deepeval.com docs, checked in-session, not
  assumed): `evaluate(test_cases, metrics)`, `LLMTestCase(input,
  actual_output, retrieval_context)`, `EvaluationDataset` built from
  `Golden`s (`input`, `expected_output`, `context`, `expected_tools` +
  metadata fields; `actual_output`/`retrieval_context`/`tools_called`
  populated at eval time), `assert_test()`/`deepeval test run` for CI-style
  checks, `metric.measure(test_case)` → `.score`, async support via
  `a_measure()`/`AsyncConfig`. Ships **50+ metrics** (confirmed current, not
  the older "30+" figure some docs pages still show) — the platform doesn't
  pick a fixed metric set, the developer's own chosen metrics apply.
  Sources: [DeepEval evaluation introduction](https://deepeval.com/docs/evaluation-introduction), [DeepEval metrics introduction](https://deepeval.com/docs/metrics-introduction), [DeepEval evaluation datasets](https://deepeval.com/docs/evaluation-datasets)
- **Dataset ingestion**: one-time conversion of a DeepEval `Golden`
  (`input`/`expected_output`/`context`) into the backend's existing
  `EvaluationDataset`/`EvaluationItem` models (same shape as today's
  `import_evaluation_dataset` flow) — no parallel DeepEval-native dataset
  system.

## 2. Telemetry reporting (v1)

- **Fire-and-forget, buffered** — `client.report(...)` never blocks the
  app's request path. Local buffer, flushed on a timer/size threshold. A
  dropped/delayed telemetry batch is acceptable; added production latency
  from reporting is not.
- **Lands in the existing `Trace`/`LLMCall` tables** — the same schema
  Langfuse import already populates, tagged with a `source` field
  (`"langfuse_import"` vs `"sdk_report"`) if anything needs to distinguish
  them later. The rule engine and V2 evidence panels must work identically
  regardless of where a trace came from.

## 3. Mode A — offline benchmark (v1)

- **Execution path**: reuse the existing `run_experiment` (backend
  `services/experiments.py`), not a new parallel engine. Make
  `_MAX_CONCURRENT_ITEMS` a per-experiment/configurable parameter instead of
  a hardcoded module constant — DeepEval-sized datasets (hundreds of
  questions) need higher throughput than the current free-tier-tuned
  default of 2, but the existing retry/backoff logic is worth keeping as-is.
- Comparison result shape (cost/quality/latency per candidate) is shared
  with Mode B's eventual result shape — see "Deferred design decisions"
  below — so downstream consumers (Decision Engine, any UI) don't need to
  know which mode produced a comparison.

## 4. Schema change: multi-metric quality (v1 — required by DeepEval integration)

`ExperimentRun.metrics`'s single scalar `quality_score` is replaced by
**`quality_scores: dict[str, float]`** — one entry per metric the experiment
declared (DeepEval metrics, or `{"correctness": ...}` for the fallback
evaluator as a degenerate one-key case). A single aggregate score hides
exactly the per-metric detail multi-metric evaluation exists to surface.

**Breaking change this forces, resolved in the same pass:** the V2 work
already shipped this session auto-advances a recommendation to
`"validated"` status via `compare_runs()`'s single `quality_difference`
compared against `QUALITY_VALIDATION_THRESHOLD = -0.05`. With
`quality_scores` as a dict, that check has no single number to compare.
**Resolution**: `"validated"` now requires **every** declared metric to
individually clear the same global `-0.05` tolerance (not a per-metric
custom tolerance — one uniform default, add per-metric tuning later only if
a real case demands it). A config that's "94% faithful but only 60%
relevant" must not validate just because one cherry-picked metric looked
fine.

**Existing dev-database rows**: no backfill migration. Pre-existing
`ExperimentRun` rows from this session's V2 work keep the old shape /
null `quality_scores` — this is same-day dev/test data, not anything a real
user depends on, consistent with skipping a compat shim for the package
rename.

## Deferred design decisions (settled in principle, not built until their slice)

These aren't open questions — they're decided, just not implemented yet,
so the next slice doesn't need to re-derive them:

- **Shadow mode sampling**: ships with a *required* sampling-rate parameter,
  no un-sampled default. Un-sampled shadow calls silently multiply real
  inference cost/latency by N — that's hidden cost, not "zero risk."
- **Traffic-split assignment**: deterministic client-side hash of an
  explicit identifier the caller must supply (e.g.
  `@optimize(..., assignment_key="user_id")`). No silent fallback to random
  assignment if no key is given — refuse rather than quietly produce
  inconsistent assignment that looks like it's working. No backend
  round-trip needed for assignment itself; the platform learns the
  assignment after the fact via telemetry reporting.
- **Primary API shape**: `@optimize(...)` decorator, not a context manager
  — fits the common one-function-one-model-call case with less boilerplate.
  Context-manager form may be offered later as an addition, never the
  headline API.
- **Tool-call capture shape** (§5, prerequisite for agent-config sweeps in
  §4): mirrors DeepEval's own `Golden.expected_tools` /
  `LLMTestCase.tools_called` shape from the start, so agent-quality
  evaluation works immediately via DeepEval's tool-use metrics with no
  translation layer built later.
- **Decision Engine (§6) trigger**: a separate, explicit call the developer
  makes after reviewing raw comparison results — never auto-surfaced the
  moment a comparison completes. Auto-surfacing presumes the developer's
  declared constraints are correct and complete before they've even seen
  the numbers.
- **Mode A/B result shape**: shared comparison structure (cost/quality/
  latency per candidate) with mode-specific metadata (sampling rate,
  assignment key, etc.) attached alongside it, not baked into a divergent
  structure per mode.

## Not yet decided (out of scope for this grilling pass — revisit when their slice starts)

- Concrete buffer flush policy for telemetry reporting (size/time
  thresholds) — an implementation tuning detail, not an architecture
  decision; pick reasonable defaults when building §2, don't over-design
  now.
- Framework adapter priority order (LangChain vs. LlamaIndex vs. raw
  OpenAI-SDK-compatible) — deferred along with the rest of §7.
- Whether parameter sweeps (§4) run sequentially or with their own
  concurrency model — deferred along with the rest of §4.

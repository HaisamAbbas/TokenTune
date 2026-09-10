Status: implemented (Phase 5)

# Run Experiments over HTTP against the sample app, not in-process

The original framing (Phase 1) assumed an Experiment would run a Workflow's pipeline as an importable, in-process function: call it once under the baseline config and once under the experiment config, diff the results. That assumption doesn't hold once there's a real target to run against. `examples/sample-rag-app` (Phase 4a/4b) is a separately containerized FastAPI service with its own process, its own dependencies (Qdrant, TEI, litellm-proxy), and its own `Agent` construction lifecycle - it is not a function the backend can import and call. Any AI application this platform targets in practice will look like this: a deployed service reachable over the network, not a library.

Given that, `app.services.experiments.run_experiment` executes each variant (baseline/experiment) by calling the sample app's `POST /api/chat` once per `EvaluationItem`, with the variant's config supplied as a per-request override (see the SDK's `OptimizerClient.get_config(override=...)`, threaded through `Agent.__init__`'s `config_override` and the REST layer's `Data.config_override` - the mechanism that makes per-request overrides possible without a container restart). The response's `usage` field (added in Phase 5 alongside this ADR, since the sample app didn't previously expose token counts) plus latency and an `AnswerCorrectnessEvaluator` judge score become the run's real metrics.

Trade-offs accepted:
- The backend now depends on the sample app being reachable at `settings.sample_rag_app_url` to run an experiment at all. There is no in-process fallback.
- A run is slower and noisier than an in-process call (real network latency, real token usage, real judge calls) - which is also exactly why the resulting numbers are trustworthy evidence for an adopt/reject decision, not simulated ones.
- Per-item failures (a single bad question, a transient timeout) are caught and recorded rather than aborting the run, since a live HTTP dependency fails in ways an in-process call wouldn't.

This generalizes cleanly to a second target application in the future: anything reachable over HTTP that accepts a per-request config override and returns real usage numbers can be experimented on the same way, with no in-process integration required.

See `backend/app/services/experiments.py`, `backend/tests/integration/test_experiments_api.py` (HTTP calls mocked - the test suite must not require the live Docker stack), and the real manual end-to-end run reported in the Phase 5 completion report for evidence this works against the actual running stack.

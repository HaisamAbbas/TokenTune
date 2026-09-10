# AI Cost Optimization Platform

Converts observability telemetry from AI applications (RAG systems, agents) into experimentally validated cost/quality recommendations. Sits above existing observability tools (Langfuse) rather than replacing them.

## Language

**Project**:
An AI application connected to the platform (e.g. one RAG system). The unit everything else — Environment, Trace, Experiment — belongs to.
_Avoid_: Application, App

**Environment**:
A deployment stage of a Project — prod, staging, or dev. Does not represent a customer or tenant; a multi-tenant deployment is a separate concept this platform doesn't model yet.
_Avoid_: Tenant, Deployment, Instance

**Workflow**:
A stable, named unit of business logic within a Project that recommendations and experiments target (e.g. `"rag_qa_pipeline"`). Assumed to be tagged consistently by the source application; drift in naming is a data-quality concern, not something the schema resolves.
_Avoid_: Pipeline, Flow, Task

**Trace**:
One execution of a Workflow, imported from an external observability source. May have no known Environment (telemetry imported before an environment was registered is valid, not an error) and may have no Workflow (untagged telemetry is still valid telemetry).

**LLM Call**:
One generation request within a Trace — a single call to a model that produces tokens and incurs cost. Does not represent retrieval or other non-generation steps; see Retrieval Step.

**Retrieval Step**:
One retrieval action within a Trace (e.g. `retriever.search()`) — modeled explicitly (top_k used, chunk count, retrieved token count) rather than inferred from an LLM Call's prompt size, so that recommendations like "reduce top_k" are based on real retrieval numbers, not guesses. Model and migration exist as of Phase 3; as of Phase 4, `LangfuseAdapter` maps `type: "retriever"` observations (produced by `examples/sample-rag-app`'s `@observe(as_type="retriever")` instrumentation) into `RetrievalStep` rows via `NormalizedRetrievalEvent`.
_Avoid_: Search, Context fetch

**Cost**:
The USD price of one LLM Call. The platform assumes USD throughout; no currency field exists because every integrated provider bills in USD.

**Normalized Telemetry Event**:
The platform's own representation of one observability event (an LLM Call or Retrieval Step), independent of any specific source's wire format. What a Telemetry Adapter produces.

**Telemetry Adapter**:
A component that fetches from one external observability source (currently Langfuse) and converts its data into Normalized Telemetry Events. Designed so a second source can be added without changing anything downstream.

**Optimization Recommendation**:
A rule engine's proposed change to a Workflow's configuration (model, top_k, prompt, or max_tokens), backed by a reason, current/proposed configuration, estimated cost impact, and confidence. Implemented in Phase 3.

**Experiment**:
A controlled run of a Workflow under an alternative configuration, compared against the same Workflow's baseline configuration on the same Evaluation Dataset. Never mutates production configuration. Not yet implemented (Phase 4).

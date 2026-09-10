from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx

from app.adapters.base import NormalizedRetrievalEvent, NormalizedTelemetryEvent, TelemetryAdapter
from app.models.project import Project

DEFAULT_BASE_URL = "https://cloud.langfuse.com"
OBSERVATIONS_PATH = "/api/public/v2/observations"

# Langfuse's `@observe(as_type="retriever")` (see examples/sample-rag-app's
# agent, which decorates its search pipeline methods with it) tags the
# resulting observation with this type, surfaced under the "core" field
# group of the v2 observations API alongside id/traceId. Anything else
# (including observations with no "type" at all, as in Langfuse's older
# "generation"-only responses) is treated as an LLM-call-shaped observation.
RETRIEVER_TYPE = "retriever"


class LangfuseAdapter(TelemetryAdapter):
    """Fetches observations from Langfuse's v2 observations API and normalizes them."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL, client: httpx.Client | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client

    def _get_client(self, project: Project) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(
            base_url=self._base_url,
            auth=(project.langfuse_public_key or "", project.langfuse_secret_key or ""),
        )

    def fetch_and_normalize(
        self, project: Project, from_ts: datetime, to_ts: datetime
    ) -> list[NormalizedTelemetryEvent | NormalizedRetrievalEvent]:
        events: list[NormalizedTelemetryEvent | NormalizedRetrievalEvent] = []
        cursor: str | None = None
        client = self._get_client(project)
        owns_client = self._client is None

        try:
            while True:
                params: dict[str, Any] = {
                    "fromStartTime": from_ts.isoformat(),
                    "toStartTime": to_ts.isoformat(),
                    # "io" (input/output) is only needed to populate
                    # RetrievalStep fields (top_k from the input kwargs,
                    # chunk_count/retrieved_tokens from the output) - it's
                    # ignored when normalizing an LLM-call-shaped observation.
                    "fields": "core,basic,usage,model,metrics,io",
                }
                if cursor:
                    params["cursor"] = cursor

                response = client.get(OBSERVATIONS_PATH, params=params)
                response.raise_for_status()
                payload = response.json()

                for observation in payload.get("data", []):
                    events.append(self._normalize(project, observation))

                cursor = payload.get("meta", {}).get("cursor")
                if not cursor:
                    break
        finally:
            if owns_client:
                client.close()

        return events

    def _normalize(
        self, project: Project, observation: dict[str, Any]
    ) -> NormalizedTelemetryEvent | NormalizedRetrievalEvent:
        core = observation.get("core") or {}
        obs_type = (core.get("type") or "").lower()

        if obs_type == RETRIEVER_TYPE:
            return self._normalize_retrieval(project, observation)
        return self._normalize_llm_call(project, observation)

    def _timestamp(self, basic: dict[str, Any]) -> datetime:
        raw_timestamp = basic.get("startTime")
        return (
            datetime.fromisoformat(raw_timestamp)
            if isinstance(raw_timestamp, str)
            else datetime.now(UTC)
        )

    def _normalize_llm_call(
        self, project: Project, observation: dict[str, Any]
    ) -> NormalizedTelemetryEvent:
        core = observation.get("core") or {}
        basic = observation.get("basic") or {}
        usage = observation.get("usage") or {}
        model_info = observation.get("model") or {}
        metrics = observation.get("metrics") or {}
        metadata = observation.get("metadata") or {}

        total_cost = usage.get("totalCost")
        trace_id: str = core.get("traceId") or ""
        model: str = model_info.get("name") or ""

        return NormalizedTelemetryEvent(
            project_id=project.id,
            trace_id=trace_id,
            span_id=core.get("id"),
            workflow=basic.get("name"),
            model=model,
            provider=model_info.get("provider"),
            input_tokens=usage.get("input", 0) or 0,
            output_tokens=usage.get("output", 0) or 0,
            total_tokens=usage.get("total", 0) or 0,
            cost=Decimal(str(total_cost)) if total_cost is not None else None,
            latency_ms=metrics.get("latency"),
            timestamp=self._timestamp(basic),
            metadata=metadata,
        )

    def _normalize_retrieval(
        self, project: Project, observation: dict[str, Any]
    ) -> NormalizedRetrievalEvent:
        """Map a `type: "retriever"` observation into a `NormalizedRetrievalEvent`.

        Shaped after examples/sample-rag-app's `@observe(as_type="retriever")`
        instrumentation on its search pipeline methods (see
        `rag.agent.Agent`): the observation's input is
        `{"args": [...], "kwargs": {"query"/"keywords": ..., "limit": ...}}`
        (Langfuse's `@observe` captures a decorated method's arguments this
        way), and its output is a `list[SearchResult]` (`{"score": float,
        "data": {"content": str, ...}}`), explicitly attached via
        `langfuse.update_current_span(output=search_results)` since the
        pipeline method itself returns a prompt-template string, not the raw
        results.
        """
        core = observation.get("core") or {}
        basic = observation.get("basic") or {}
        io = observation.get("io") or {}
        metadata = observation.get("metadata") or {}

        trace_id: str = core.get("traceId") or ""

        input_kwargs = (io.get("input") or {}).get("kwargs") or {}
        top_k = input_kwargs.get("limit")

        output = io.get("output")
        chunks = output if isinstance(output, list) else []
        chunk_count = len(chunks) if isinstance(output, list) else None
        retrieved_tokens = self._estimate_retrieved_tokens(chunks) if chunks else None

        return NormalizedRetrievalEvent(
            project_id=project.id,
            trace_id=trace_id,
            span_id=core.get("id"),
            top_k=top_k,
            chunk_count=chunk_count,
            retrieved_tokens=retrieved_tokens,
            timestamp=self._timestamp(basic),
            metadata=metadata,
        )

    def _estimate_retrieved_tokens(self, chunks: list[Any]) -> int | None:
        """Whitespace-split token estimate over each chunk's `data.content`.

        A rough approximation (same spirit as the app's own token counting),
        not a real tokenizer count - good enough for Rule A's "excessive
        retrieval context" reasoning without depending on a tokenizer per
        provider/model.
        """
        total = 0
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            content = (chunk.get("data") or {}).get("content")
            if isinstance(content, str):
                total += len(content.split())
        return total or None

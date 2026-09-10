from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx

from app.adapters.base import NormalizedTelemetryEvent, TelemetryAdapter
from app.models.project import Project

DEFAULT_BASE_URL = "https://cloud.langfuse.com"
OBSERVATIONS_PATH = "/api/public/v2/observations"


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
    ) -> list[NormalizedTelemetryEvent]:
        events: list[NormalizedTelemetryEvent] = []
        cursor: str | None = None
        client = self._get_client(project)
        owns_client = self._client is None

        try:
            while True:
                params: dict[str, Any] = {
                    "fromStartTime": from_ts.isoformat(),
                    "toStartTime": to_ts.isoformat(),
                    "fields": "core,basic,usage,model,metrics",
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

    def _normalize(self, project: Project, observation: dict[str, Any]) -> NormalizedTelemetryEvent:
        core = observation.get("core") or {}
        basic = observation.get("basic") or {}
        usage = observation.get("usage") or {}
        model_info = observation.get("model") or {}
        metrics = observation.get("metrics") or {}
        metadata = observation.get("metadata") or {}

        total_cost = usage.get("totalCost")
        raw_timestamp = basic.get("startTime")
        timestamp = (
            datetime.fromisoformat(raw_timestamp)
            if isinstance(raw_timestamp, str)
            else datetime.now(UTC)
        )
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
            timestamp=timestamp,
            metadata=metadata,
        )

import atexit
import logging
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from tokentune.config import ExperimentConfig

logger = logging.getLogger(__name__)

# V1 scoping decision: get_config() reads its values from local environment
# variables rather than fetching from a live backend API. This is a real
# simplification, not the intended end state: `project_slug`/`environment`
# are accepted here for forward compatibility with a future call that looks
# up an experiment-assigned config from the platform backend, but today they
# are unused. A field left unset (None) means "use the calling app's own
# default" — it does NOT mean "ask the platform for the production value".
_ENV_PREFIX = "TOKENTUNE_"

# report() is fire-and-forget: buffered locally and flushed on a background
# thread, never blocking the caller's request path. A dropped/delayed
# telemetry batch on process exit is an acceptable tradeoff; added
# request-path latency from reporting is not (see SDK spec decision log).
_DEFAULT_FLUSH_INTERVAL_SECONDS = 5.0
_DEFAULT_MAX_BUFFER_SIZE = 100


@dataclass
class ReportedCall:
    """One SDK-mediated call's outcome, queued by `report()` for the
    background flusher to send to the platform's telemetry-ingest endpoint."""

    project_slug: str
    trace_id: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost: float | None = None
    quality_score: float | None = None
    workflow: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class _BackgroundFlusher:
    """Buffers `ReportedCall`s and sends them to the platform's
    `/sdk/telemetry/report` endpoint on a background daemon thread - flushed
    on a timer or once the buffer hits `max_buffer_size`, plus a best-effort
    flush on process exit. Never raises back into the caller: a failed send
    (network down, backend unreachable) is logged and the batch is dropped,
    since a lost telemetry batch is an acceptable tradeoff but blocking or
    crashing the app's own request path is not."""

    def __init__(
        self,
        backend_url: str,
        flush_interval: float | None = None,
        max_buffer_size: int | None = None,
    ) -> None:
        # Falls back to the module-level defaults at call time (not as a
        # bound default argument) so tests can monkeypatch
        # _DEFAULT_FLUSH_INTERVAL_SECONDS/_DEFAULT_MAX_BUFFER_SIZE and have
        # it actually take effect.
        self._backend_url = backend_url.rstrip("/")
        self._flush_interval = (
            flush_interval if flush_interval is not None else _DEFAULT_FLUSH_INTERVAL_SECONDS
        )
        self._max_buffer_size = (
            max_buffer_size if max_buffer_size is not None else _DEFAULT_MAX_BUFFER_SIZE
        )
        self._buffer: list[ReportedCall] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        atexit.register(self.flush)

    def add(self, call: ReportedCall) -> None:
        with self._lock:
            self._buffer.append(call)
            should_flush_now = len(self._buffer) >= self._max_buffer_size
        if should_flush_now:
            self.flush()

    def _run(self) -> None:
        while not self._stop_event.wait(self._flush_interval):
            self.flush()

    def flush(self) -> None:
        with self._lock:
            if not self._buffer:
                return
            batch, self._buffer = self._buffer, []
        self._send(batch)

    def _send(self, batch: list[ReportedCall]) -> None:
        payload: dict[str, Any] = {
            "project_slug": batch[0].project_slug,
            "items": [
                {
                    "trace_id": call.trace_id,
                    "model": call.model,
                    "input_tokens": call.input_tokens,
                    "output_tokens": call.output_tokens,
                    "latency_ms": call.latency_ms,
                    "cost": call.cost,
                    "quality_score": call.quality_score,
                    "workflow": call.workflow,
                    "timestamp": call.timestamp.isoformat(),
                }
                for call in batch
            ],
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                client.post(f"{self._backend_url}/sdk/telemetry/report", json=payload)
        except httpx.HTTPError:
            logger.warning(
                "tokentune: failed to report a batch of %d call(s) - dropped, not retried",
                len(batch),
                exc_info=True,
            )


class OptimizerClient:
    """Entry point an AI application uses to connect to the platform.

    V1: identifies the project/environment, returns the production
    configuration via `get_config()`, and reports live call outcomes back to
    the platform via `report()`. Experiment variant assignment (Mode B: live
    shadow/traffic-split experiments) is added in a later version - v1's
    `get_config()` never asks the backend for an assigned variant.
    """

    def __init__(
        self,
        project_slug: str,
        environment: str = "production",
        backend_url: str | None = None,
    ) -> None:
        self.project_slug = project_slug
        self.environment = environment
        # get_config() never needs this - it's purely env-var based (see
        # its own docstring). Only report() needs somewhere to send data.
        self._backend_url = backend_url or os.environ.get(f"{_ENV_PREFIX}BACKEND_URL")
        self._flusher: _BackgroundFlusher | None = None
        self._warned_missing_backend_url = False

    def get_config(self, override: ExperimentConfig | None = None) -> ExperimentConfig:
        """Return the config an app should apply for this project/environment.

        See the module-level comment: V1 reads its baseline from environment
        variables (`TOKENTUNE_MODEL`, `TOKENTUNE_TOP_K`,
        `TOKENTUNE_PROMPT`, `TOKENTUNE_MAX_TOKENS`), not from a live
        backend call. Unset variables map to `None` fields, which callers
        should treat as "no override" rather than "fetch failed".

        Phase 5 addition: `override` lets a single call site (e.g. one HTTP
        request) supply a per-request config that takes precedence over the
        env vars for that call only, without touching the process
        environment or requiring a restart. Any field left `None` on
        `override` falls back to the env-var value (which may itself be
        `None`, meaning "no override at any level").
        """
        env_config = ExperimentConfig(
            model=os.environ.get(f"{_ENV_PREFIX}MODEL") or None,
            top_k=_int_or_none(os.environ.get(f"{_ENV_PREFIX}TOP_K")),
            prompt=os.environ.get(f"{_ENV_PREFIX}PROMPT") or None,
            max_tokens=_int_or_none(os.environ.get(f"{_ENV_PREFIX}MAX_TOKENS")),
        )
        if override is None:
            return env_config
        return ExperimentConfig(
            model=override.model or env_config.model,
            top_k=override.top_k or env_config.top_k,
            prompt=override.prompt or env_config.prompt,
            max_tokens=override.max_tokens or env_config.max_tokens,
        )

    def report(
        self,
        *,
        trace_id: str | None = None,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        cost: float | None = None,
        quality_score: float | None = None,
        workflow: str | None = None,
    ) -> None:
        """Report one SDK-mediated call's outcome back to the platform.

        Fire-and-forget: buffered locally and sent on a background thread.
        Never blocks or raises for the caller - a network failure while
        sending is logged, not propagated, since reporting must never become
        a new failure mode for the app's actual request. `trace_id`
        correlates this call across retries/steps; auto-generated if omitted
        (each `report()` call is then treated as its own trace).

        Requires `backend_url` (constructor arg or `TOKENTUNE_BACKEND_URL`
        env var) - `get_config()` works without one, this doesn't. If never
        configured, this logs one warning and silently no-ops thereafter
        rather than raising into the caller's request path.
        """
        if self._backend_url is None:
            if not self._warned_missing_backend_url:
                logger.warning(
                    "tokentune: report() called but no backend_url configured "
                    "(pass backend_url=... or set %sBACKEND_URL) - telemetry will "
                    "not be sent.",
                    _ENV_PREFIX,
                )
                self._warned_missing_backend_url = True
            return

        if self._flusher is None:
            self._flusher = _BackgroundFlusher(self._backend_url)

        call = ReportedCall(
            project_slug=self.project_slug,
            trace_id=trace_id or str(uuid.uuid4()),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost=cost,
            quality_score=quality_score,
            workflow=workflow,
        )
        self._flusher.add(call)


def _int_or_none(value: str | None) -> int | None:
    return int(value) if value else None

import logging
import time

import pytest

from tokentune import client as client_module
from tokentune.client import OptimizerClient


class _RecordingHttpClient:
    """Stands in for httpx.Client so tests never make a real network call.
    Records every POST body; raises on `.post()` when configured to
    simulate the platform being unreachable."""

    sent: list[dict] = []
    should_fail = False

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def __enter__(self) -> "_RecordingHttpClient":
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def post(self, url: str, json: dict) -> None:
        if self.should_fail:
            raise client_module.httpx.ConnectError("backend unreachable")
        self.sent.append({"url": url, "json": json})


@pytest.fixture(autouse=True)
def _reset_recording_client(monkeypatch: pytest.MonkeyPatch) -> None:
    _RecordingHttpClient.sent = []
    _RecordingHttpClient.should_fail = False
    monkeypatch.setattr(client_module.httpx, "Client", _RecordingHttpClient)
    # Flush fast in tests instead of waiting the real 5s default interval.
    monkeypatch.setattr(client_module, "_DEFAULT_FLUSH_INTERVAL_SECONDS", 0.05)


def test_report_without_backend_url_logs_warning_and_does_not_raise(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = OptimizerClient(project_slug="sample-rag-app")
    with caplog.at_level(logging.WARNING):
        client.report(model="gpt-4o-mini", input_tokens=100, output_tokens=20, latency_ms=250.0)

    assert "no backend_url configured" in caplog.text
    assert _RecordingHttpClient.sent == []


def test_report_flushes_batch_to_backend_url() -> None:
    client = OptimizerClient(project_slug="sample-rag-app", backend_url="http://localhost:9999")
    client.report(
        trace_id="trace-1",
        model="gpt-4o-mini",
        input_tokens=100,
        output_tokens=20,
        latency_ms=250.0,
        cost=0.001,
        quality_score=0.9,
        workflow="rag-answer",
    )

    client._flusher.flush()  # type: ignore[union-attr]

    assert len(_RecordingHttpClient.sent) == 1
    sent = _RecordingHttpClient.sent[0]
    assert sent["url"] == "http://localhost:9999/sdk/telemetry/report"
    assert sent["json"]["project_slug"] == "sample-rag-app"
    item = sent["json"]["items"][0]
    assert item["trace_id"] == "trace-1"
    assert item["model"] == "gpt-4o-mini"
    assert item["cost"] == 0.001
    assert item["quality_score"] == 0.9
    assert item["workflow"] == "rag-answer"


def test_report_generates_trace_id_when_omitted() -> None:
    client = OptimizerClient(project_slug="sample-rag-app", backend_url="http://localhost:9999")
    client.report(model="gpt-4o-mini", input_tokens=10, output_tokens=5, latency_ms=100.0)

    client._flusher.flush()  # type: ignore[union-attr]

    item = _RecordingHttpClient.sent[0]["json"]["items"][0]
    assert item["trace_id"]  # non-empty, auto-generated


def test_report_never_raises_when_backend_is_unreachable() -> None:
    _RecordingHttpClient.should_fail = True
    client = OptimizerClient(project_slug="sample-rag-app", backend_url="http://localhost:9999")

    client.report(model="gpt-4o-mini", input_tokens=10, output_tokens=5, latency_ms=100.0)
    client._flusher.flush()  # type: ignore[union-attr]  # must not raise


def test_report_auto_flushes_on_buffer_size_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client_module, "_DEFAULT_MAX_BUFFER_SIZE", 2)
    client = OptimizerClient(project_slug="sample-rag-app", backend_url="http://localhost:9999")

    client.report(model="gpt-4o-mini", input_tokens=1, output_tokens=1, latency_ms=1.0)
    assert _RecordingHttpClient.sent == []
    client.report(model="gpt-4o-mini", input_tokens=1, output_tokens=1, latency_ms=1.0)

    assert len(_RecordingHttpClient.sent) == 1
    assert len(_RecordingHttpClient.sent[0]["json"]["items"]) == 2


def test_report_auto_flushes_on_background_timer() -> None:
    client = OptimizerClient(project_slug="sample-rag-app", backend_url="http://localhost:9999")
    client.report(model="gpt-4o-mini", input_tokens=1, output_tokens=1, latency_ms=1.0)

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and not _RecordingHttpClient.sent:
        time.sleep(0.02)

    assert len(_RecordingHttpClient.sent) == 1

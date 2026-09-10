from datetime import UTC, datetime, timedelta

from app.schemas.telemetry import TelemetryImportRequest


def test_naive_datetime_is_coerced_to_utc() -> None:
    request = TelemetryImportRequest(
        from_ts=datetime(2026, 1, 1),  # noqa: DTZ001 - intentionally naive
        to_ts=datetime(2026, 2, 1),  # noqa: DTZ001 - intentionally naive
    )
    assert request.from_ts.tzinfo == UTC
    assert request.to_ts.tzinfo == UTC


def test_aware_datetime_is_preserved() -> None:
    aware = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=5)
    request = TelemetryImportRequest(from_ts=aware, to_ts=aware)
    assert request.from_ts == aware

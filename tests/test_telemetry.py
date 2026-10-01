from datetime import UTC, datetime

from shema_platform.foundation.telemetry import (
    InMemoryTelemetrySink,
    TelemetryEvent,
    build_event,
)


def test_telemetry_allowlists_operational_attributes() -> None:
    event = build_event(
        name="http.request.completed",
        correlation_id="corr-1",
        attributes={
            "route": "/v1/orders",
            "status": 200,
            "duration_ms": 18,
            "authorization": "Bearer secret-token",
            "body": "sensitive-payload",
            "provider": "max",
        },
    )

    assert event.attributes == {
        "route": "/v1/orders",
        "status": 200,
        "duration_ms": 18,
        "provider": "max",
    }


def test_telemetry_truncates_long_strings() -> None:
    event = build_event(
        name="job.failed",
        correlation_id="corr-1",
        attributes={"error_code": "x" * 1000},
    )

    assert len(event.attributes["error_code"]) == 256


def test_telemetry_requires_timezone_aware_timestamp() -> None:
    try:
        TelemetryEvent(
            name="test",
            occurred_at=datetime(2026, 1, 1),
            correlation_id="corr-1",
            attributes={},
        )
    except ValueError as exc:
        assert "timezone-aware" in str(exc)
    else:
        raise AssertionError("expected timezone validation failure")


def test_telemetry_sink_is_non_authoritative_and_append_only_for_observation() -> None:
    sink = InMemoryTelemetrySink()
    event = build_event(
        name="http.request.completed",
        correlation_id="corr-1",
        occurred_at=datetime.now(UTC),
    )

    sink.emit(event)

    assert sink.all() == (event,)

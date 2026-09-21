import json
import logging
from datetime import UTC, datetime

from shema_platform.foundation.observability import (
    InMemoryTelemetry,
    JsonLoggingTelemetry,
    TelemetryEvent,
    TelemetryLevel,
    emit_safely,
)


def test_telemetry_redacts_sensitive_attributes_recursively() -> None:
    sink = InMemoryTelemetry()
    sink.emit(
        TelemetryEvent(
            name="test.event",
            occurred_at=datetime.now(UTC),
            attributes={
                "authorization": "Bearer secret",
                "nested": {"api_key": "secret", "safe": "value"},
            },
        )
    )

    payload = sink.events[0].as_dict()
    assert payload["attributes"]["authorization"] == "[REDACTED]"
    assert payload["attributes"]["nested"]["api_key"] == "[REDACTED]"
    assert payload["attributes"]["nested"]["safe"] == "value"


def test_json_logging_sink_emits_structured_json(caplog) -> None:
    logger = logging.getLogger("test.telemetry")
    sink = JsonLoggingTelemetry(logger)

    with caplog.at_level(logging.INFO, logger="test.telemetry"):
        sink.emit(
            TelemetryEvent(
                name="job.completed",
                occurred_at=datetime.now(UTC),
                attributes={"attempt": 2},
            )
        )

    payload = json.loads(caplog.records[-1].message)
    assert payload["name"] == "job.completed"
    assert payload["attributes"]["attempt"] == 2


def test_telemetry_failure_is_non_authoritative() -> None:
    class BrokenTelemetry:
        def emit(self, event: TelemetryEvent) -> None:
            raise RuntimeError("sink down")

    emit_safely(
        BrokenTelemetry(),
        TelemetryEvent(
            name="test.event",
            occurred_at=datetime.now(UTC),
            level=TelemetryLevel.ERROR,
        ),
    )

from __future__ import annotations

import dataclasses
import datetime
import types
from collections.abc import Mapping
from typing import Protocol


_SAFE_ATTRIBUTE_KEYS = frozenset(
    {
        "component",
        "operation",
        "route",
        "status",
        "duration_ms",
        "attempt",
        "provider",
        "error_code",
        "job_type",
    }
)
_MAX_STRING_VALUE_LENGTH = 256


@dataclasses.dataclass(frozen=True, slots=True)
class TelemetryEvent:
    name: str
    occurred_at: datetime.datetime
    correlation_id: str
    attributes: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("telemetry event name is required")
        if not self.correlation_id.strip():
            raise ValueError("correlation_id is required")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")

        safe = _sanitize_attributes(self.attributes)
        object.__setattr__(self, "attributes", types.MappingProxyType(safe))


class TelemetrySink(Protocol):
    """Non-authoritative operational telemetry boundary."""

    def emit(self, event: TelemetryEvent) -> None: ...


class NoopTelemetrySink:
    """Production-safe default sink until an external telemetry backend is composed."""

    def emit(self, event: TelemetryEvent) -> None:
        return None


class InMemoryTelemetrySink:
    """Deterministic sink used by tests and local runtime composition."""

    def __init__(self) -> None:
        self._events: list[TelemetryEvent] = []

    def emit(self, event: TelemetryEvent) -> None:
        self._events.append(event)

    def all(self) -> tuple[TelemetryEvent, ...]:
        return tuple(self._events)


def build_event(
    *,
    name: str,
    correlation_id: str,
    attributes: Mapping[str, object] | None = None,
    occurred_at: datetime.datetime | None = None,
) -> TelemetryEvent:
    return TelemetryEvent(
        name=name,
        occurred_at=occurred_at or datetime.datetime.now(datetime.UTC),
        correlation_id=correlation_id,
        attributes=attributes or {},
    )


def _sanitize_attributes(
    attributes: Mapping[str, object],
) -> dict[str, object]:
    safe: dict[str, object] = {}
    for key, value in attributes.items():
        if key not in _SAFE_ATTRIBUTE_KEYS:
            continue
        if isinstance(value, bool) or isinstance(value, int) or isinstance(value, float):
            safe[key] = value
        elif isinstance(value, str):
            safe[key] = value[:_MAX_STRING_VALUE_LENGTH]
    return safe

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol


class TelemetryLevel(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


_SENSITIVE_KEYS = frozenset(
    {
        "authorization",
        "access_token",
        "refresh_token",
        "id_token",
        "token",
        "password",
        "secret",
        "client_secret",
        "api_key",
        "private_key",
    }
)


def _redact(value: Any, *, key: str | None = None) -> Any:
    if key is not None and key.lower() in _SENSITIVE_KEYS:
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {
            str(item_key): _redact(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class TelemetryEvent:
    name: str
    occurred_at: datetime
    level: TelemetryLevel = TelemetryLevel.INFO
    correlation_id: str | None = None
    actor_id: str | None = None
    job_id: str | None = None
    entity_id: str | None = None
    attributes: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("telemetry event name is required")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        object.__setattr__(
            self,
            "attributes",
            _redact({} if self.attributes is None else self.attributes),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "occurred_at": self.occurred_at.astimezone(UTC).isoformat(),
            "level": self.level.value,
            "correlation_id": self.correlation_id,
            "actor_id": self.actor_id,
            "job_id": self.job_id,
            "entity_id": self.entity_id,
            "attributes": dict(self.attributes or {}),
        }


class TelemetryPort(Protocol):
    def emit(self, event: TelemetryEvent) -> None: ...


class NullTelemetry:
    def emit(self, event: TelemetryEvent) -> None:
        return None


class InMemoryTelemetry:
    def __init__(self) -> None:
        self.events: list[TelemetryEvent] = []

    def emit(self, event: TelemetryEvent) -> None:
        self.events.append(event)


class JsonLoggingTelemetry:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("shema.telemetry")

    def emit(self, event: TelemetryEvent) -> None:
        level = {
            TelemetryLevel.INFO: logging.INFO,
            TelemetryLevel.WARNING: logging.WARNING,
            TelemetryLevel.ERROR: logging.ERROR,
        }[event.level]
        self._logger.log(
            level,
            json.dumps(
                event.as_dict(),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
        )


def emit_safely(telemetry: TelemetryPort, event: TelemetryEvent) -> None:
    try:
        telemetry.emit(event)
    except Exception:
        return None


def now_utc() -> datetime:
    return datetime.now(UTC)

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol


class MaxEventKind(StrEnum):
    MESSAGE = "message"
    CALLBACK = "callback"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class MaxWebhookEvent:
    event_id: str
    api_version: str
    kind: MaxEventKind
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CanonicalCommunicationEvent:
    event_id: str
    channel: str
    kind: str
    external_version: str
    payload: dict[str, Any]


class MaxAdapter(Protocol):
    def normalize(self, event: MaxWebhookEvent) -> CanonicalCommunicationEvent: ...


class MaxMockAdapter:
    """Deterministic adapter used by contract tests; performs no network access."""

    def normalize(self, event: MaxWebhookEvent) -> CanonicalCommunicationEvent:
        if not event.event_id:
            raise ValueError("MAX event_id is required")
        if not event.api_version:
            raise ValueError("MAX api_version is required")
        return CanonicalCommunicationEvent(
            event_id=event.event_id,
            channel="max",
            kind=event.kind.value,
            external_version=event.api_version,
            payload=dict(event.payload),
        )

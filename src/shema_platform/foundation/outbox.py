from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class OutboxStatus(StrEnum):
    PENDING = "pending"
    PUBLISHED = "published"


@dataclass(frozen=True, slots=True)
class OutboxEvent:
    event_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: dict[str, Any]
    occurred_at: datetime
    status: OutboxStatus = OutboxStatus.PENDING


class OutboxStore:
    """In-memory reference implementation of the transactional outbox contract."""

    def __init__(self) -> None:
        self._events: dict[str, OutboxEvent] = {}

    def append(self, event: OutboxEvent) -> OutboxEvent:
        if event.event_id in self._events:
            return self._events[event.event_id]
        self._events[event.event_id] = event
        return event

    def pending(self) -> tuple[OutboxEvent, ...]:
        return tuple(
            event for event in self._events.values() if event.status is OutboxStatus.PENDING
        )

    def mark_published(self, event_id: str) -> OutboxEvent:
        event = self._events[event_id]
        published = OutboxEvent(
            event_id=event.event_id,
            event_type=event.event_type,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            payload=dict(event.payload),
            occurred_at=event.occurred_at,
            status=OutboxStatus.PUBLISHED,
        )
        self._events[event_id] = published
        return published


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

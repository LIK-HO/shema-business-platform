from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from .errors import IntegrityViolation


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


@dataclass(frozen=True, slots=True)
class OutboxDelivery:
    """Immutable event plus the current worker delivery lease."""

    event: OutboxEvent
    attempt: int
    worker_id: str
    lease_until: datetime

    def __post_init__(self) -> None:
        if self.attempt < 1:
            raise ValueError("attempt must be >= 1")
        if not self.worker_id.strip():
            raise ValueError("worker_id is required")
        if self.lease_until.tzinfo is None:
            raise ValueError("lease_until must be timezone-aware")


class OutboxStore:
    """In-memory reference implementation of the transactional outbox contract."""

    def __init__(self) -> None:
        self._events: dict[str, OutboxEvent] = {}

    def append(self, event: OutboxEvent) -> OutboxEvent:
        existing = self._events.get(event.event_id)
        if existing is not None:
            if existing != event:
                raise IntegrityViolation("outbox event_id collision with different event")
            return existing
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
    return datetime.now(UTC)

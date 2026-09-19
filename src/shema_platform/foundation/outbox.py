from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
        self._leases: dict[str, OutboxDelivery] = {}

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

    def claim_pending(
        self,
        worker_id: str,
        *,
        lease_seconds: int,
        now: datetime,
        limit: int,
    ) -> tuple[OutboxDelivery, ...]:
        if not worker_id.strip():
            raise ValueError("worker_id is required")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be > 0")
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")

        selected: list[OutboxDelivery] = []
        for event in sorted(
            self.pending(),
            key=lambda item: (item.occurred_at, item.event_id),
        ):
            lease = self._leases.get(event.event_id)
            if lease is not None and lease.lease_until > now:
                continue
            delivery = OutboxDelivery(
                event=event,
                attempt=lease.attempt + 1 if lease is not None else 1,
                worker_id=worker_id,
                lease_until=now + timedelta(seconds=lease_seconds),
            )
            self._leases[event.event_id] = delivery
            selected.append(delivery)
            if len(selected) >= limit:
                break
        return tuple(selected)

    def mark_published(
        self,
        event_id: str,
        worker_id: str,
        *,
        now: datetime,
    ) -> OutboxEvent:
        lease = self._leases.get(event_id)
        if lease is None or lease.worker_id != worker_id:
            raise IntegrityViolation(
                "outbox publication rejected: missing or different worker lease"
            )
        if lease.lease_until <= now:
            raise IntegrityViolation(
                "outbox publication rejected: missing or expired delivery lease"
            )

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
        self._leases.pop(event_id, None)
        return published


def utc_now() -> datetime:
    return datetime.now(UTC)

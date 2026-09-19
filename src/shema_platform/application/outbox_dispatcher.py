from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from shema_platform.application.ports import UnitOfWork
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.outbox import OutboxEvent, OutboxStatus


class OutboxPublisher(Protocol):
    """External publisher; implementations must deduplicate immutable event_id."""

    def publish(self, event: OutboxEvent) -> None: ...


class OutboxDispatcher:
    """At-least-once external publication over the transactional outbox."""

    def __init__(
        self,
        unit_of_work_factory: Callable[[], UnitOfWork],
        publisher: OutboxPublisher,
        *,
        worker_id: str = "outbox-worker",
    ) -> None:
        if not worker_id.strip():
            raise ValueError("worker_id is required")
        self._unit_of_work_factory = unit_of_work_factory
        self._publisher = publisher
        self._worker_id = worker_id

    def dispatch_pending(self, *, limit: int = 100) -> int:
        if limit < 1:
            raise ValueError("limit must be >= 1")

        with self._unit_of_work_factory() as uow:
            pending = uow.outbox.pending()[:limit]

        published = 0
        for event in pending:
            if event.status is not OutboxStatus.PENDING:
                continue

            self._publisher.publish(event)

            with self._unit_of_work_factory() as uow:
                current = uow.outbox.pending()
                if not any(item.event_id == event.event_id for item in current):
                    continue

                delivered = uow.outbox.mark_published(event.event_id)
                published_at = datetime.now(UTC)
                uow.audits.append(
                    AuditRecord(
                        audit_id=str(uuid5(NAMESPACE_URL, f"audit:outbox.published:{event.event_id}")),
                        actor_id=self._worker_id,
                        action="outbox.published",
                        resource_type="outbox_event",
                        resource_id=event.event_id,
                        outcome="success",
                        occurred_at=published_at,
                        metadata={
                            "event_type": event.event_type,
                            "aggregate_type": event.aggregate_type,
                            "aggregate_id": event.aggregate_id,
                        },
                    )
                )
                published += 1

        return published

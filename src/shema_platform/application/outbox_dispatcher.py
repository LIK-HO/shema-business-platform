from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from shema_platform.application.ports import UnitOfWork
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.outbox import OutboxDelivery, OutboxEvent


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
        lease_seconds: int = 60,
    ) -> None:
        if not worker_id.strip():
            raise ValueError("worker_id is required")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be > 0")
        self._unit_of_work_factory = unit_of_work_factory
        self._publisher = publisher
        self._worker_id = worker_id
        self._lease_seconds = lease_seconds

    def dispatch_pending(self, *, limit: int = 100) -> int:
        if limit < 1:
            raise ValueError("limit must be >= 1")

        with self._unit_of_work_factory() as uow:
            deliveries = uow.outbox.claim_pending(
                self._worker_id,
                lease_seconds=self._lease_seconds,
                now=datetime.now(UTC),
                limit=limit,
            )

        published = 0
        for delivery in deliveries:
            try:
                self._publisher.publish(delivery.event)
            except Exception as exc:
                self._audit_delivery_failure(delivery, exc)
                raise

            with self._unit_of_work_factory() as uow:
                uow.outbox.mark_published(
                    delivery.event.event_id,
                    self._worker_id,
                    now=datetime.now(UTC),
                )
                uow.audits.append(
                    AuditRecord(
                        audit_id=str(
                            uuid5(
                                NAMESPACE_URL,
                                f"audit:outbox.published:{delivery.event.event_id}",
                            )
                        ),
                        actor_id=self._worker_id,
                        action="outbox.published",
                        resource_type="outbox_event",
                        resource_id=delivery.event.event_id,
                        outcome="success",
                        occurred_at=datetime.now(UTC),
                        metadata={
                            "event_type": delivery.event.event_type,
                            "aggregate_type": delivery.event.aggregate_type,
                            "aggregate_id": delivery.event.aggregate_id,
                            "delivery_attempt": delivery.attempt,
                        },
                    )
                )
                published += 1

        return published

    def _audit_delivery_failure(
        self,
        delivery: OutboxDelivery,
        error: Exception,
    ) -> None:
        try:
            with self._unit_of_work_factory() as uow:
                uow.audits.append(
                    AuditRecord(
                        audit_id=str(
                            uuid5(
                                NAMESPACE_URL,
                                (
                                    "audit:outbox.failed:"
                                    f"{delivery.event.event_id}:{delivery.attempt}"
                                ),
                            )
                        ),
                        actor_id=self._worker_id,
                        action="outbox.publish_failed",
                        resource_type="outbox_event",
                        resource_id=delivery.event.event_id,
                        outcome="failure",
                        occurred_at=datetime.now(UTC),
                        metadata={
                            "event_type": delivery.event.event_type,
                            "aggregate_type": delivery.event.aggregate_type,
                            "aggregate_id": delivery.event.aggregate_id,
                            "delivery_attempt": delivery.attempt,
                            "error": str(error),
                        },
                    )
                )
        except Exception:
            # The publisher error remains the authoritative failure signal.
            pass

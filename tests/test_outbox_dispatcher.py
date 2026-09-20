from datetime import UTC, datetime, timedelta

import pytest

from shema_platform.application.outbox_dispatcher import OutboxDispatcher
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.observability import InMemoryTelemetry
from shema_platform.foundation.outbox import OutboxDelivery, OutboxEvent, OutboxStatus


class FakeOutbox:
    def __init__(self, events: list[OutboxEvent]) -> None:
        self.events = {event.event_id: event for event in events}
        self.leases: dict[str, OutboxDelivery] = {}

    def append(self, event: OutboxEvent) -> OutboxEvent:
        self.events[event.event_id] = event
        return event

    def pending(self) -> tuple[OutboxEvent, ...]:
        return tuple(
            event for event in self.events.values()
            if event.status is OutboxStatus.PENDING
        )

    def claim_pending(
        self,
        worker_id: str,
        *,
        lease_seconds: int,
        now: datetime,
        limit: int,
    ) -> tuple[OutboxDelivery, ...]:
        selected: list[OutboxDelivery] = []
        for event in sorted(self.pending(), key=lambda item: item.event_id):
            lease = self.leases.get(event.event_id)
            if lease is not None and lease.lease_until > now:
                continue
            delivery = OutboxDelivery(
                event=event,
                attempt=(lease.attempt + 1 if lease is not None else 1),
                worker_id=worker_id,
                lease_until=now + timedelta(seconds=lease_seconds),
            )
            self.leases[event.event_id] = delivery
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
        delivery = self.leases.get(event_id)
        if delivery is None or delivery.worker_id != worker_id:
            raise RuntimeError("delivery lease rejected")
        if delivery.lease_until <= now:
            raise RuntimeError("delivery lease expired")
        event = self.events[event_id]
        published = OutboxEvent(
            event_id=event.event_id,
            event_type=event.event_type,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            payload=dict(event.payload),
            occurred_at=event.occurred_at,
            status=OutboxStatus.PUBLISHED,
        )
        self.events[event_id] = published
        self.leases.pop(event_id, None)
        return published


class FakeUoW:
    def __init__(self, outbox: FakeOutbox) -> None:
        self.outbox = outbox
        self.audits: list[AuditRecord] = []

    def __enter__(self) -> "FakeUoW":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        return False


class FakePublisher:
    def __init__(self) -> None:
        self.published: list[str] = []
        self.fail = False

    def publish(self, event: OutboxEvent) -> None:
        if self.fail:
            raise RuntimeError("publisher unavailable")
        self.published.append(event.event_id)


def make_event(event_id: str = "event-1") -> OutboxEvent:
    return OutboxEvent(
        event_id=event_id,
        event_type="job.completed",
        aggregate_type="job",
        aggregate_id="job-1",
        payload={"state": "succeeded"},
        occurred_at=datetime.now(UTC),
    )


def test_outbox_dispatcher_publishes_and_marks_event() -> None:
    outbox = FakeOutbox([make_event()])
    uow = FakeUoW(outbox)
    publisher = FakePublisher()
    telemetry = InMemoryTelemetry()
    dispatcher = OutboxDispatcher(lambda: uow, publisher, telemetry=telemetry)

    assert dispatcher.dispatch_pending() == 1
    assert publisher.published == ["event-1"]
    assert outbox.events["event-1"].status is OutboxStatus.PUBLISHED
    assert uow.audits[0].action == "outbox.published"
    assert [event.name for event in telemetry.events] == [
        "outbox.claimed",
        "outbox.published",
    ]


def test_outbox_dispatcher_leaves_event_pending_when_publish_fails() -> None:
    outbox = FakeOutbox([make_event()])
    uow = FakeUoW(outbox)
    publisher = FakePublisher()
    publisher.fail = True
    telemetry = InMemoryTelemetry()
    dispatcher = OutboxDispatcher(lambda: uow, publisher, telemetry=telemetry)

    with pytest.raises(RuntimeError, match="publisher unavailable"):
        dispatcher.dispatch_pending()

    assert outbox.events["event-1"].status is OutboxStatus.PENDING
    assert uow.audits[0].action == "outbox.publish_failed"
    assert [event.name for event in telemetry.events] == [
        "outbox.claimed",
        "outbox.publish_failed",
    ]


def test_outbox_dispatcher_respects_limit() -> None:
    outbox = FakeOutbox([make_event("event-1"), make_event("event-2")])
    uow = FakeUoW(outbox)
    publisher = FakePublisher()
    dispatcher = OutboxDispatcher(lambda: uow, publisher)

    assert dispatcher.dispatch_pending(limit=1) == 1
    assert publisher.published == ["event-1"]
    assert outbox.events["event-2"].status is OutboxStatus.PENDING


def test_outbox_lease_prevents_second_worker_until_expiry() -> None:
    outbox = FakeOutbox([make_event()])
    first = outbox.claim_pending(
        "worker-1",
        lease_seconds=10,
        now=datetime(2026, 9, 20, 0, 0, tzinfo=UTC),
        limit=1,
    )
    assert len(first) == 1

    second = outbox.claim_pending(
        "worker-2",
        lease_seconds=10,
        now=datetime(2026, 9, 20, 0, 0, 1, tzinfo=UTC),
        limit=1,
    )
    assert second == ()

    reclaimed = outbox.claim_pending(
        "worker-2",
        lease_seconds=10,
        now=datetime(2026, 9, 20, 0, 10, tzinfo=UTC),
        limit=1,
    )
    assert len(reclaimed) == 1
    assert reclaimed[0].attempt == 2
    assert reclaimed[0].worker_id == "worker-2"

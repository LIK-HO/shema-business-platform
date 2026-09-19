from datetime import UTC, datetime

import pytest

from shema_platform.application.outbox_dispatcher import OutboxDispatcher
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.outbox import OutboxEvent, OutboxStatus


class FakeOutbox:
    def __init__(self, events: list[OutboxEvent]) -> None:
        self.events = {event.event_id: event for event in events}

    def append(self, event: OutboxEvent) -> OutboxEvent:
        self.events[event.event_id] = event
        return event

    def pending(self) -> tuple[OutboxEvent, ...]:
        return tuple(
            event for event in self.events.values()
            if event.status is OutboxStatus.PENDING
        )

    def mark_published(self, event_id: str) -> OutboxEvent:
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
        return published


class FakeUoW:
    def __init__(self, outbox: FakeOutbox) -> None:
        self.outbox = outbox
        self.audits: list[AuditRecord] = []

    def __enter__(self) -> "FakeUoW":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        return False

    def append(self, record: AuditRecord) -> None:
        self.audits.append(record)


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
    dispatcher = OutboxDispatcher(lambda: uow, publisher)

    assert dispatcher.dispatch_pending() == 1
    assert publisher.published == ["event-1"]
    assert outbox.events["event-1"].status is OutboxStatus.PUBLISHED
    assert uow.audits[0].action == "outbox.published"


def test_outbox_dispatcher_leaves_event_pending_when_publish_fails() -> None:
    outbox = FakeOutbox([make_event()])
    uow = FakeUoW(outbox)
    publisher = FakePublisher()
    publisher.fail = True
    dispatcher = OutboxDispatcher(lambda: uow, publisher)

    with pytest.raises(RuntimeError, match="publisher unavailable"):
        dispatcher.dispatch_pending()

    assert outbox.events["event-1"].status is OutboxStatus.PENDING
    assert uow.audits == []


def test_outbox_dispatcher_respects_limit() -> None:
    outbox = FakeOutbox([make_event("event-1"), make_event("event-2")])
    uow = FakeUoW(outbox)
    publisher = FakePublisher()
    dispatcher = OutboxDispatcher(lambda: uow, publisher)

    assert dispatcher.dispatch_pending(limit=1) == 1
    assert publisher.published == ["event-1"]
    assert outbox.events["event-2"].status is OutboxStatus.PENDING

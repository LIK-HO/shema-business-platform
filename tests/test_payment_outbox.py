from __future__ import annotations

import pytest

from shema_platform.application.job_runner import PermanentJobError
from shema_platform.application.payment_outbox import PaymentOutboxHandler
from shema_platform.foundation.outbox import OutboxEvent


class FakeExecution:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def __call__(self, *, payment_id: str, attempt_id: str) -> str:
        self.calls.append((payment_id, attempt_id))
        return "ok"


def event(**payload: object) -> OutboxEvent:
    from datetime import UTC, datetime

    return OutboxEvent(
        event_id="event-1",
        event_type="payment.create_requested",
        aggregate_type="payment",
        aggregate_id="payment-1",
        payload=dict(payload),
        occurred_at=datetime.now(UTC),
    )


def test_payment_outbox_handler_dispatches_valid_event() -> None:
    execution = FakeExecution()
    handler = PaymentOutboxHandler(execution)

    assert handler.handle(
        event(payment_id="payment-1", attempt_id="attempt-1")
    ) == "ok"
    assert execution.calls == [("payment-1", "attempt-1")]


def test_payment_outbox_handler_rejects_invalid_event() -> None:
    handler = PaymentOutboxHandler(FakeExecution())

    with pytest.raises(PermanentJobError, match="missing payment_id"):
        handler.handle(event(attempt_id="attempt-1"))


def test_payment_outbox_handler_rejects_wrong_aggregate() -> None:
    handler = PaymentOutboxHandler(FakeExecution())
    invalid = OutboxEvent(
        event_id="event-2",
        event_type="payment.create_requested",
        aggregate_type="order",
        aggregate_id="payment-1",
        payload={"payment_id": "payment-1", "attempt_id": "attempt-1"},
        occurred_at=event().occurred_at,
    )

    with pytest.raises(PermanentJobError, match="aggregate type"):
        handler.handle(invalid)

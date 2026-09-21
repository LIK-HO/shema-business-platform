from __future__ import annotations

from typing import Protocol

from shema_platform.application.job_runner import PermanentJobError
from shema_platform.foundation.outbox import OutboxEvent


class PaymentOutboxExecution(Protocol):
    def __call__(
        self,
        *,
        payment_id: str,
        attempt_id: str,
    ) -> object: ...


class PaymentOutboxHandler:
    """Bridges durable payment outbox intent to the external payment execution workflow."""

    EVENT_TYPE = "payment.create_requested"

    def __init__(self, workflow: PaymentOutboxExecution) -> None:
        self._workflow = workflow

    def handle(self, event: OutboxEvent) -> object:
        if event.event_type != self.EVENT_TYPE:
            raise PermanentJobError(
                f"unsupported payment outbox event: {event.event_type}"
            )
        if event.aggregate_type != "payment":
            raise PermanentJobError("payment outbox event has invalid aggregate type")

        payment_id = event.payload.get("payment_id")
        attempt_id = event.payload.get("attempt_id")
        if not isinstance(payment_id, str) or not payment_id.strip():
            raise PermanentJobError("payment outbox event is missing payment_id")
        if not isinstance(attempt_id, str) or not attempt_id.strip():
            raise PermanentJobError("payment outbox event is missing attempt_id")
        if event.aggregate_id != payment_id:
            raise PermanentJobError("payment outbox aggregate does not match payment_id")

        return self._workflow(
            payment_id=payment_id,
            attempt_id=attempt_id,
        )

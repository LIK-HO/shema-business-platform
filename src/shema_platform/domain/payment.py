from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from shema_platform.domain.money import Money


class PaymentIntentStatus(StrEnum):
    DRAFT = "draft"
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PaymentAttemptStatus(StrEnum):
    READY = "ready"
    SENDING = "sending"
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"


class ProviderEventStatus(StrEnum):
    RECEIVED = "received"
    PROCESSED = "processed"
    IGNORED = "ignored"


@dataclass(frozen=True, slots=True)
class PaymentIntent:
    payment_id: str
    order_id: str
    amount: Money
    idempotency_key: str
    status: PaymentIntentStatus = PaymentIntentStatus.DRAFT

    def __post_init__(self) -> None:
        if not self.payment_id.strip():
            raise ValueError("payment_id is required")
        if not self.order_id.strip():
            raise ValueError("order_id is required")
        if not self.idempotency_key.strip():
            raise ValueError("idempotency_key is required")
        if self.amount.amount <= 0:
            raise ValueError("payment amount must be positive")

    def begin(self) -> PaymentIntent:
        if self.status is not PaymentIntentStatus.DRAFT:
            raise ValueError("only draft payment can begin")
        return self._with_status(PaymentIntentStatus.PENDING)

    def mark_processing(self) -> PaymentIntent:
        if self.status is not PaymentIntentStatus.PENDING:
            raise ValueError("only pending payment can start processing")
        return self._with_status(PaymentIntentStatus.PROCESSING)

    def succeed(self) -> PaymentIntent:
        if self.status not in {
            PaymentIntentStatus.PENDING,
            PaymentIntentStatus.PROCESSING,
        }:
            raise ValueError("payment cannot succeed from current state")
        return self._with_status(PaymentIntentStatus.SUCCEEDED)

    def fail(self) -> PaymentIntent:
        if self.status not in {
            PaymentIntentStatus.PENDING,
            PaymentIntentStatus.PROCESSING,
        }:
            raise ValueError("payment cannot fail from current state")
        return self._with_status(PaymentIntentStatus.FAILED)

    def cancel(self) -> PaymentIntent:
        if self.status not in {
            PaymentIntentStatus.DRAFT,
            PaymentIntentStatus.PENDING,
        }:
            raise ValueError("payment cannot be cancelled from current state")
        return self._with_status(PaymentIntentStatus.CANCELLED)

    def _with_status(self, status: PaymentIntentStatus) -> PaymentIntent:
        return PaymentIntent(
            payment_id=self.payment_id,
            order_id=self.order_id,
            amount=self.amount,
            idempotency_key=self.idempotency_key,
            status=status,
        )


@dataclass(frozen=True, slots=True)
class PaymentAttempt:
    attempt_id: str
    payment_id: str
    attempt_number: int
    external_idempotency_key: str
    status: PaymentAttemptStatus = PaymentAttemptStatus.READY
    provider_ref: str | None = None
    worker_id: str | None = None
    lease_until: datetime | None = None

    def __post_init__(self) -> None:
        if not self.attempt_id.strip() or not self.payment_id.strip():
            raise ValueError("payment attempt identifiers are required")
        if self.attempt_number < 1:
            raise ValueError("attempt_number must be >= 1")
        if not self.external_idempotency_key.strip():
            raise ValueError("external_idempotency_key is required")
        if self.status is PaymentAttemptStatus.SENDING:
            if not self.worker_id or self.lease_until is None:
                raise ValueError("sending payment attempt requires worker lease")

    def reserve(self, worker_id: str, lease_until: datetime) -> PaymentAttempt:
        if not worker_id.strip():
            raise ValueError("worker_id is required")
        if self.status is PaymentAttemptStatus.SENDING:
            if self.lease_until is not None and self.lease_until > lease_until:
                raise ValueError("active payment attempt lease cannot be replaced")
        elif self.status is not PaymentAttemptStatus.READY:
            raise ValueError("payment attempt is not ready")
        if lease_until.tzinfo is None:
            raise ValueError("lease_until must be timezone-aware")
        return PaymentAttempt(
            attempt_id=self.attempt_id,
            payment_id=self.payment_id,
            attempt_number=self.attempt_number,
            external_idempotency_key=self.external_idempotency_key,
            status=PaymentAttemptStatus.SENDING,
            provider_ref=self.provider_ref,
            worker_id=worker_id,
            lease_until=lease_until,
        )

    def mark_pending(self, provider_ref: str | None = None) -> PaymentAttempt:
        self._require_live_lease()
        return PaymentAttempt(
            attempt_id=self.attempt_id,
            payment_id=self.payment_id,
            attempt_number=self.attempt_number,
            external_idempotency_key=self.external_idempotency_key,
            status=PaymentAttemptStatus.PENDING,
            provider_ref=provider_ref or self.provider_ref,
        )

    def succeed(self, provider_ref: str | None = None) -> PaymentAttempt:
        self._require_live_lease()
        return PaymentAttempt(
            attempt_id=self.attempt_id,
            payment_id=self.payment_id,
            attempt_number=self.attempt_number,
            external_idempotency_key=self.external_idempotency_key,
            status=PaymentAttemptStatus.SUCCEEDED,
            provider_ref=provider_ref or self.provider_ref,
        )

    def fail(self, provider_ref: str | None = None) -> PaymentAttempt:
        self._require_live_lease()
        return PaymentAttempt(
            attempt_id=self.attempt_id,
            payment_id=self.payment_id,
            attempt_number=self.attempt_number,
            external_idempotency_key=self.external_idempotency_key,
            status=PaymentAttemptStatus.FAILED,
            provider_ref=provider_ref or self.provider_ref,
        )

    def expire(self) -> PaymentAttempt:
        if self.status not in {
            PaymentAttemptStatus.SENDING,
            PaymentAttemptStatus.PENDING,
        }:
            raise ValueError("only active payment attempt can expire")
        return PaymentAttempt(
            attempt_id=self.attempt_id,
            payment_id=self.payment_id,
            attempt_number=self.attempt_number,
            external_idempotency_key=self.external_idempotency_key,
            status=PaymentAttemptStatus.EXPIRED,
            provider_ref=self.provider_ref,
        )

    def _require_live_lease(self) -> None:
        if self.status is not PaymentAttemptStatus.SENDING:
            raise ValueError("payment attempt must be sending")
        if self.worker_id is None or self.lease_until is None:
            raise ValueError("payment attempt lease is missing")


@dataclass(frozen=True, slots=True)
class ProviderEvent:
    event_id: str
    provider_ref: str
    event_type: str
    signature_verified: bool
    payload_hash: str
    received_at: datetime
    status: ProviderEventStatus = ProviderEventStatus.RECEIVED

    def __post_init__(self) -> None:
        if not self.event_id.strip() or not self.provider_ref.strip():
            raise ValueError("provider event identifiers are required")
        if not self.event_type.strip():
            raise ValueError("event_type is required")
        if not self.signature_verified:
            raise ValueError("provider event signature must be verified")
        if not self.payload_hash.strip():
            raise ValueError("payload_hash is required")
        if self.received_at.tzinfo is None:
            raise ValueError("received_at must be timezone-aware")

    def processed(self) -> ProviderEvent:
        if self.status is not ProviderEventStatus.RECEIVED:
            raise ValueError("provider event is not awaiting processing")
        return ProviderEvent(
            event_id=self.event_id,
            provider_ref=self.provider_ref,
            event_type=self.event_type,
            signature_verified=True,
            payload_hash=self.payload_hash,
            received_at=self.received_at,
            status=ProviderEventStatus.PROCESSED,
        )

    def ignored(self) -> ProviderEvent:
        if self.status is not ProviderEventStatus.RECEIVED:
            raise ValueError("provider event is not awaiting processing")
        return ProviderEvent(
            event_id=self.event_id,
            provider_ref=self.provider_ref,
            event_type=self.event_type,
            signature_verified=True,
            payload_hash=self.payload_hash,
            received_at=self.received_at,
            status=ProviderEventStatus.IGNORED,
        )

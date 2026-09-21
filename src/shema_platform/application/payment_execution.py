from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from hashlib import sha256
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from shema_platform.application.commands import Actor
from shema_platform.application.ports import UnitOfWork
from shema_platform.domain.economics import EconomicEntry, EconomicKind
from shema_platform.domain.money import Money
from shema_platform.domain.order import OrderStatus
from shema_platform.domain.payment import (
    PaymentAttempt,
    PaymentAttemptStatus,
    PaymentIntent,
    PaymentIntentStatus,
    ProviderEvent,
    ProviderEventStatus,
)
from shema_platform.domain.payment_adjustment import (
    PaymentAdjustment,
    PaymentAdjustmentKind,
)
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.authorization import Permission, RBACAuthorizer
from shema_platform.foundation.errors import (
    IdempotencyConflict,
    IntegrityViolation,
    PolicyDenied,
)
from shema_platform.foundation.outbox import OutboxEvent, utc_now
from shema_platform.foundation.policy import Decision, PolicyContext, PolicyEngine


class PaymentExecutionState(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class PaymentProviderResult:
    provider_ref: str
    status: PaymentAttemptStatus
    amount: Money


@dataclass(frozen=True, slots=True)
class VerifiedPaymentEvent:
    event: ProviderEvent
    amount: Money
    source_payment_ref: str
    payment_status: PaymentAttemptStatus | None = None
    adjustment_kind: PaymentAdjustmentKind | None = None


class PaymentProviderAdapter(Protocol):
    """Provider-neutral transport contract.

    Implementations must use the supplied external idempotency key for every
    charge/create effect and must never write platform persistence directly.
    """

    provider_name: str

    def create_payment(
        self,
        payment: PaymentIntent,
        attempt: PaymentAttempt,
    ) -> PaymentProviderResult: ...

    def verify_webhook(
        self,
        *,
        headers: Mapping[str, str],
        payload: bytes,
    ) -> VerifiedPaymentEvent: ...


class PaymentGateway:
    """Provider adapter guardrail around outbound payment effects."""

    def __init__(self, adapter: PaymentProviderAdapter) -> None:
        self._adapter = adapter

    def create_payment(
        self,
        payment: PaymentIntent,
        attempt: PaymentAttempt,
    ) -> PaymentProviderResult:
        if attempt.status is not PaymentAttemptStatus.SENDING:
            raise IntegrityViolation("payment attempt must be sending before provider call")
        result = self._adapter.create_payment(payment, attempt)
        if not result.provider_ref.strip():
            raise IntegrityViolation("payment provider returned no provider reference")
        if result.status not in {
            PaymentAttemptStatus.PENDING,
            PaymentAttemptStatus.SUCCEEDED,
            PaymentAttemptStatus.FAILED,
        }:
            raise IntegrityViolation("provider returned invalid payment state")
        if result.amount.currency != payment.amount.currency:
            raise IntegrityViolation("provider payment currency does not match intent")
        if result.amount != payment.amount:
            raise IntegrityViolation("provider payment amount does not match intent")
        return result

    def verify_webhook(
        self,
        *,
        headers: Mapping[str, str],
        payload: bytes,
    ) -> VerifiedPaymentEvent:
        result = self._adapter.verify_webhook(headers=headers, payload=payload)
        if not result.event.signature_verified:
            raise IntegrityViolation("payment webhook signature is not verified")
        if not result.source_payment_ref.strip():
            raise IntegrityViolation("webhook source payment reference is required")
        if result.amount.amount <= 0:
            raise IntegrityViolation("webhook payment amount must be positive")
        if result.adjustment_kind is None:
            if result.payment_status not in {
                PaymentAttemptStatus.PENDING,
                PaymentAttemptStatus.SUCCEEDED,
                PaymentAttemptStatus.FAILED,
            }:
                raise IntegrityViolation("webhook returned invalid payment state")
        elif result.payment_status is not None:
            raise IntegrityViolation(
                "adjustment webhook cannot also carry payment state"
            )
        return result


@dataclass(frozen=True, slots=True)
class PaymentCreationResult:
    payment_id: str
    order_id: str
    amount: str
    currency: str
    status: PaymentIntentStatus


class PaymentCreationWorkflow:
    """Creates a durable payment intent from immutable order truth."""

    def __init__(
        self,
        unit_of_work_factory: Callable[[], UnitOfWork],
        authorizer: RBACAuthorizer,
        policy: PolicyEngine,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._authorizer = authorizer
        self._policy = policy

    @staticmethod
    def request_hash(order_id: str, idempotency_key: str) -> str:
        return sha256(
            f"{order_id}\n{idempotency_key}".encode()
        ).hexdigest()

    @staticmethod
    def payment_id(idempotency_key: str) -> str:
        return str(uuid5(NAMESPACE_URL, f"payment:{idempotency_key}"))

    def create(
        self,
        *,
        actor: Actor,
        order_id: str,
        idempotency_key: str,
    ) -> PaymentCreationResult:
        self._authorizer.require(actor.actor_id, Permission.PAYMENT_CREATE)
        if not idempotency_key.strip():
            raise ValueError("idempotency_key is required")

        with self._unit_of_work_factory() as uow:
            order = uow.orders.get(order_id)
            if order is None:
                raise KeyError(f"unknown order: {order_id}")
            if order.status in {OrderStatus.CANCELLED, OrderStatus.FAILED}:
                raise PolicyDenied(
                    "payment cannot be created for a terminal failed/cancelled order"
                )

            decision = self._policy.evaluate(
                PolicyContext(
                    actor_id=actor.actor_id,
                    action="payment_create",
                    resource_type="order",
                    resource_id=order_id,
                    actor_trust_level=actor.trust_level,
                    resource_trust_level=2,
                )
            )
            if decision.decision is not Decision.ALLOW:
                raise PolicyDenied(decision.reason)

            request_hash = self.request_hash(order_id, idempotency_key)
            existing = uow.idempotency.get(idempotency_key)
            if existing is not None:
                if existing.request_hash != request_hash:
                    raise IdempotencyConflict(
                        "payment idempotency key reused for a different order"
                    )
                payment = uow.payments.get(existing.result_ref)
                if payment is None:
                    raise IntegrityViolation(
                        "payment idempotency result has no durable payment intent"
                    )
                return self._result(payment)

            payment_id = self.payment_id(idempotency_key)
            uow.idempotency.reserve(
                idempotency_key,
                request_hash,
                payment_id,
            )
            payment = PaymentIntent(
                payment_id=payment_id,
                order_id=order_id,
                amount=order.total,
                idempotency_key=idempotency_key,
            ).begin()
            uow.payments.add(payment)

            attempt = PaymentAttempt(
                attempt_id=str(uuid5(NAMESPACE_URL, f"payment-attempt:{payment_id}:1")),
                payment_id=payment_id,
                attempt_number=1,
                external_idempotency_key=f"payment-effect:{payment_id}:1",
            )
            uow.payment_attempts.add(attempt)

            event = OutboxEvent(
                event_id=str(uuid5(NAMESPACE_URL, f"payment.create:{payment_id}")),
                event_type="payment.create_requested",
                aggregate_type="payment",
                aggregate_id=payment_id,
                payload={
                    "payment_id": payment_id,
                    "order_id": order_id,
                    "amount": str(order.total.amount),
                    "currency": order.total.currency,
                    "attempt_id": attempt.attempt_id,
                },
                occurred_at=utc_now(),
            )
            uow.outbox.append(event)
            uow.audits.append(
                AuditRecord(
                    audit_id=str(uuid5(NAMESPACE_URL, f"audit:payment.create:{payment_id}")),
                    actor_id=actor.actor_id,
                    action="payment.created",
                    resource_type="payment",
                    resource_id=payment_id,
                    outcome="success",
                    occurred_at=event.occurred_at,
                    metadata={
                        "order_id": order_id,
                        "amount": str(payment.amount.amount),
                        "currency": payment.amount.currency,
                    },
                )
            )
            return self._result(payment)

    @staticmethod
    def _result(payment: PaymentIntent) -> PaymentCreationResult:
        return PaymentCreationResult(
            payment_id=payment.payment_id,
            order_id=payment.order_id,
            amount=str(payment.amount.amount),
            currency=payment.amount.currency,
            status=payment.status,
        )


class PaymentExecutionWorkflow:
    """Executes one reserved external payment effect outside the DB transaction."""

    SEND_LEASE_SECONDS = 300

    def __init__(
        self,
        unit_of_work_factory: Callable[[], UnitOfWork],
        gateway: PaymentGateway,
        *,
        worker_id: str,
    ) -> None:
        if not worker_id.strip():
            raise ValueError("worker_id is required")
        self._unit_of_work_factory = unit_of_work_factory
        self._gateway = gateway
        self._worker_id = worker_id

    def execute(self, *, payment_id: str, attempt_id: str) -> PaymentExecutionState:
        now = utc_now()
        with self._unit_of_work_factory() as uow:
            payment = uow.payments.get(payment_id)
            attempt = uow.payment_attempts.get(attempt_id)
            if payment is None or attempt is None:
                raise KeyError("payment or attempt not found")
            if attempt.payment_id != payment_id:
                raise IntegrityViolation("payment attempt references another payment")
            if payment.status is PaymentIntentStatus.SUCCEEDED:
                return PaymentExecutionState.SUCCEEDED
            if payment.status in {
                PaymentIntentStatus.FAILED,
                PaymentIntentStatus.CANCELLED,
            }:
                raise PolicyDenied("terminal payment cannot execute")
            if payment.status is PaymentIntentStatus.PENDING:
                payment = payment.mark_processing()
                uow.payments.save(payment)

            sending = uow.payment_attempts.claim_for_send(
                attempt_id,
                self._worker_id,
                lease_until=now + timedelta(seconds=self.SEND_LEASE_SECONDS),
                now=now,
            )

        result = self._gateway.create_payment(payment, sending)

        with self._unit_of_work_factory() as uow:
            current = uow.payments.get(payment_id)
            if current is None:
                raise KeyError(f"unknown payment: {payment_id}")

            if result.amount != current.amount:
                raise IntegrityViolation("provider payment amount does not match intent")

            final_attempt = uow.payment_attempts.complete(
                attempt_id,
                self._worker_id,
                status=result.status,
                provider_ref=result.provider_ref,
                now=utc_now(),
            )

            event_type = f"payment.{result.status.value}"
            if result.status is PaymentAttemptStatus.SUCCEEDED:
                if current.status is not PaymentIntentStatus.SUCCEEDED:
                    current = current.succeed()
                    uow.payments.save(current)
                self._record_revenue(uow, current)
            elif result.status is PaymentAttemptStatus.FAILED:
                if current.status is not PaymentIntentStatus.FAILED:
                    if current.status in {
                        PaymentIntentStatus.PENDING,
                        PaymentIntentStatus.PROCESSING,
                    }:
                        current = current.fail()
                        uow.payments.save(current)
                    else:
                        raise IntegrityViolation("payment failure conflicts with terminal state")
            else:
                if current.status is PaymentIntentStatus.PENDING:
                    current = current.mark_processing()
                    uow.payments.save(current)

            event = OutboxEvent(
                event_id=str(
                    uuid5(
                        NAMESPACE_URL,
                        f"{event_type}:{payment_id}:{final_attempt.attempt_number}",
                    )
                ),
                event_type=event_type,
                aggregate_type="payment",
                aggregate_id=payment_id,
                payload={
                    "payment_id": payment_id,
                    "order_id": current.order_id,
                    "attempt_id": attempt_id,
                    "provider_ref": result.provider_ref,
                    "status": result.status.value,
                },
                occurred_at=utc_now(),
            )
            uow.outbox.append(event)
            uow.audits.append(
                AuditRecord(
                    audit_id=str(
                        uuid5(
                            NAMESPACE_URL,
                            f"audit:{event_type}:{payment_id}:{final_attempt.attempt_number}",
                        )
                    ),
                    actor_id=self._worker_id,
                    action=event_type,
                    resource_type="payment",
                    resource_id=payment_id,
                    outcome="success",
                    occurred_at=event.occurred_at,
                    metadata={
                        "attempt_id": attempt_id,
                        "provider_ref": result.provider_ref,
                        "status": result.status.value,
                    },
                )
            )
            return PaymentExecutionState(result.status.value)

    @staticmethod
    def _record_revenue(uow: UnitOfWork, payment: PaymentIntent) -> None:
        source_ref = f"payment-revenue:{payment.payment_id}"
        existing = uow.economics.list_for_entity(payment.order_id)
        if any(
            entry.kind is EconomicKind.REVENUE and entry.source_ref == source_ref
            for entry in existing
        ):
            return
        uow.economics.add(
            EconomicEntry(
                entry_id=str(uuid5(NAMESPACE_URL, f"economic:{source_ref}")),
                entity_ref=payment.order_id,
                kind=EconomicKind.REVENUE,
                amount=payment.amount,
                source_ref=source_ref,
                occurred_at=utc_now(),
            )
        )


@dataclass(frozen=True, slots=True)
class PaymentWebhookResult:
    event_id: str
    status: str
    payment_id: str | None


class PaymentWebhookWorkflow:
    """Consumes verified provider events and keeps payment state monotonic."""

    def __init__(
        self,
        unit_of_work_factory: Callable[[], UnitOfWork],
        gateway: PaymentGateway,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._gateway = gateway

    def process(
        self,
        *,
        headers: Mapping[str, str],
        payload: bytes,
    ) -> PaymentWebhookResult:
        verified = self._gateway.verify_webhook(headers=headers, payload=payload)
        event = verified.event

        with self._unit_of_work_factory() as uow:
            existing = uow.provider_events.get(event.event_id)
            if existing is not None:
                return PaymentWebhookResult(
                    event_id=event.event_id,
                    status="duplicate",
                    payment_id=None,
                )

            uow.provider_events.add(event)
            attempt = uow.payment_attempts.find_by_provider_ref(
                verified.source_payment_ref
            )
            if attempt is None:
                uow.quarantine.add(
                    object_type="payment_provider_event",
                    object_ref=event.event_id,
                    reason_code="provider_payment_unmatched",
                    payload={
                        "provider_ref": event.provider_ref,
                        "source_payment_ref": verified.source_payment_ref,
                        "event_type": event.event_type,
                    },
                )
                uow.provider_events.mark_processed(
                    event.event_id,
                    status=ProviderEventStatus.IGNORED,
                    processed_at=utc_now(),
                )
                uow.audits.append(
                    AuditRecord(
                        audit_id=str(
                            uuid5(
                                NAMESPACE_URL,
                                f"audit:payment.unmatched:{event.event_id}",
                            )
                        ),
                        actor_id="payment-provider",
                        action="payment.provider_event_unmatched",
                        resource_type="provider_event",
                        resource_id=event.event_id,
                        outcome="review",
                        occurred_at=utc_now(),
                        metadata={
                            "provider_ref": event.provider_ref,
                            "source_payment_ref": verified.source_payment_ref,
                        },
                    )
                )
                return PaymentWebhookResult(
                    event_id=event.event_id,
                    status="unmatched",
                    payment_id=None,
                )

            payment = uow.payments.get(attempt.payment_id)
            if payment is None:
                uow.quarantine.add(
                    object_type="payment_provider_event",
                    object_ref=event.event_id,
                    reason_code="payment_missing_for_provider_event",
                    payload={
                        "provider_ref": event.provider_ref,
                        "source_payment_ref": verified.source_payment_ref,
                        "payment_id": attempt.payment_id,
                    },
                )
                uow.provider_events.mark_processed(
                    event.event_id,
                    status=ProviderEventStatus.IGNORED,
                    processed_at=utc_now(),
                )
                return PaymentWebhookResult(
                    event_id=event.event_id,
                    status="quarantined",
                    payment_id=None,
                )

            if verified.adjustment_kind is not None:
                if payment.status is not PaymentIntentStatus.SUCCEEDED:
                    raise IntegrityViolation(
                        "payment adjustment requires a succeeded payment"
                    )
                existing_adjustment = uow.payment_adjustments.get_by_provider_event(
                    event.event_id
                )
                if existing_adjustment is not None:
                    uow.provider_events.mark_processed(
                        event.event_id,
                        status=ProviderEventStatus.PROCESSED,
                        processed_at=utc_now(),
                    )
                    return PaymentWebhookResult(
                        event_id=event.event_id,
                        status=verified.adjustment_kind.value,
                        payment_id=payment.payment_id,
                    )

                adjusted_total = uow.payment_adjustments.total_for_payment(
                    payment.payment_id
                ).add(verified.amount)
                if adjusted_total.amount > payment.amount.amount:
                    raise IntegrityViolation(
                        "cumulative payment adjustments exceed captured payment"
                    )

                adjustment = PaymentAdjustment(
                    adjustment_id=str(
                        uuid5(
                            NAMESPACE_URL,
                            f"payment-adjustment:{event.event_id}",
                        )
                    ),
                    payment_id=payment.payment_id,
                    provider_event_id=event.event_id,
                    provider_ref=event.provider_ref,
                    kind=verified.adjustment_kind,
                    amount=verified.amount,
                    occurred_at=event.received_at,
                )
                uow.payment_adjustments.add(adjustment)
                uow.economics.add(
                    EconomicEntry(
                        entry_id=str(
                            uuid5(
                                NAMESPACE_URL,
                                f"economic-adjustment:{adjustment.adjustment_id}",
                            )
                        ),
                        entity_ref=payment.order_id,
                        kind=EconomicKind.ADJUSTMENT,
                        amount=Money(
                            -verified.amount.amount,
                            verified.amount.currency,
                        ),
                        source_ref=f"payment-adjustment:{adjustment.adjustment_id}",
                        occurred_at=adjustment.occurred_at,
                    )
                )
                uow.outbox.append(
                    OutboxEvent(
                        event_id=str(
                            uuid5(
                                NAMESPACE_URL,
                                f"payment.adjustment:{event.event_id}",
                            )
                        ),
                        event_type=f"payment.{verified.adjustment_kind.value}",
                        aggregate_type="payment",
                        aggregate_id=payment.payment_id,
                        payload={
                            "payment_id": payment.payment_id,
                            "provider_ref": event.provider_ref,
                            "event_id": event.event_id,
                            "kind": verified.adjustment_kind.value,
                            "amount": str(verified.amount.amount),
                            "currency": verified.amount.currency,
                        },
                        occurred_at=utc_now(),
                    )
                )
                uow.audits.append(
                    AuditRecord(
                        audit_id=str(
                            uuid5(
                                NAMESPACE_URL,
                                f"audit:payment.adjustment:{event.event_id}",
                            )
                        ),
                        actor_id="payment-provider",
                        action=f"payment.{verified.adjustment_kind.value}",
                        resource_type="payment",
                        resource_id=payment.payment_id,
                        outcome="success",
                        occurred_at=utc_now(),
                        metadata={
                            "provider_ref": event.provider_ref,
                            "amount": str(verified.amount.amount),
                            "currency": verified.amount.currency,
                        },
                    )
                )
                uow.provider_events.mark_processed(
                    event.event_id,
                    status=ProviderEventStatus.PROCESSED,
                    processed_at=utc_now(),
                )
                return PaymentWebhookResult(
                    event_id=event.event_id,
                    status=verified.adjustment_kind.value,
                    payment_id=payment.payment_id,
                )

            if verified.amount != payment.amount:
                raise IntegrityViolation(
                    "webhook payment amount does not match intent"
                )

            payment_changed = False
            event_status = verified.payment_status
            if event_status is PaymentAttemptStatus.SUCCEEDED:
                if payment.status is PaymentIntentStatus.SUCCEEDED:
                    pass
                elif payment.status in {
                    PaymentIntentStatus.PENDING,
                    PaymentIntentStatus.PROCESSING,
                }:
                    uow.payment_attempts.apply_provider_result(
                        attempt.attempt_id,
                        status=PaymentAttemptStatus.SUCCEEDED,
                        provider_ref=event.provider_ref,
                    )
                    payment = payment.succeed()
                    uow.payments.save(payment)
                    PaymentExecutionWorkflow._record_revenue(uow, payment)
                    payment_changed = True
                else:
                    uow.quarantine.add(
                        object_type="payment_provider_event",
                        object_ref=event.event_id,
                        reason_code="payment_state_conflict",
                        payload={
                            "payment_id": payment.payment_id,
                            "current_status": payment.status.value,
                            "observed_status": event_status.value,
                            "provider_ref": event.provider_ref,
                        },
                    )
                    uow.provider_events.mark_processed(
                        event.event_id,
                        status=ProviderEventStatus.IGNORED,
                        processed_at=utc_now(),
                    )
                    return PaymentWebhookResult(
                        event_id=event.event_id,
                        status="quarantined",
                        payment_id=payment.payment_id,
                    )
            elif event_status is PaymentAttemptStatus.FAILED:
                if payment.status in {
                    PaymentIntentStatus.PENDING,
                    PaymentIntentStatus.PROCESSING,
                }:
                    uow.payment_attempts.apply_provider_result(
                        attempt.attempt_id,
                        status=PaymentAttemptStatus.FAILED,
                        provider_ref=event.provider_ref,
                    )
                    payment = payment.fail()
                    uow.payments.save(payment)
                    payment_changed = True
                elif payment.status is PaymentIntentStatus.FAILED:
                    pass
                else:
                    uow.quarantine.add(
                        object_type="payment_provider_event",
                        object_ref=event.event_id,
                        reason_code="payment_state_conflict",
                        payload={
                            "payment_id": payment.payment_id,
                            "current_status": payment.status.value,
                            "observed_status": event_status.value,
                            "provider_ref": event.provider_ref,
                        },
                    )
                    uow.provider_events.mark_processed(
                        event.event_id,
                        status=ProviderEventStatus.IGNORED,
                        processed_at=utc_now(),
                    )
                    return PaymentWebhookResult(
                        event_id=event.event_id,
                        status="quarantined",
                        payment_id=payment.payment_id,
                    )
            else:
                uow.payment_attempts.apply_provider_result(
                    attempt.attempt_id,
                    status=PaymentAttemptStatus.PENDING,
                    provider_ref=event.provider_ref,
                )

            if payment_changed:
                event_type = f"payment.webhook.{event_status.value}"
                uow.outbox.append(
                    OutboxEvent(
                        event_id=str(
                            uuid5(
                                NAMESPACE_URL,
                                f"{event_type}:{event.event_id}",
                            )
                        ),
                        event_type=event_type,
                        aggregate_type="payment",
                        aggregate_id=payment.payment_id,
                        payload={
                            "payment_id": payment.payment_id,
                            "provider_ref": event.provider_ref,
                            "event_id": event.event_id,
                            "status": event_status.value,
                        },
                        occurred_at=utc_now(),
                    )
                )

            uow.provider_events.mark_processed(
                event.event_id,
                status=ProviderEventStatus.PROCESSED,
                processed_at=utc_now(),
            )
            uow.audits.append(
                AuditRecord(
                    audit_id=str(
                        uuid5(
                            NAMESPACE_URL,
                            f"audit:payment.webhook:{event.event_id}",
                        )
                    ),
                    actor_id="payment-provider",
                    action="payment.provider_event_processed",
                    resource_type="provider_event",
                    resource_id=event.event_id,
                    outcome=(
                        "success"
                        if payment_changed or payment.status is PaymentIntentStatus.SUCCEEDED
                        else "review"
                    ),
                    occurred_at=utc_now(),
                    metadata={
                        "provider_ref": event.provider_ref,
                        "payment_id": payment.payment_id,
                        "event_type": event.event_type,
                        "provider_status": event_status.value,
                    },
                )
            )

            return PaymentWebhookResult(
                event_id=event.event_id,
                status=event_status.value,
                payment_id=payment.payment_id,
            )

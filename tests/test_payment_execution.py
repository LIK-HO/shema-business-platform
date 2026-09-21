from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from shema_platform.application.commands import Actor
from shema_platform.application.payment_execution import (
    PaymentCreationWorkflow,
    PaymentExecutionState,
    PaymentExecutionWorkflow,
    PaymentGateway,
    PaymentProviderAdapter,
    PaymentProviderResult,
    PaymentWebhookWorkflow,
    VerifiedPaymentEvent,
)
from shema_platform.domain.economics import EconomicEntry, EconomicKind
from shema_platform.domain.money import Money
from shema_platform.domain.order import Order, OrderLine, OrderStatus
from shema_platform.domain.payment import (
    PaymentAttempt,
    PaymentAttemptStatus,
    PaymentIntent,
    PaymentIntentStatus,
    ProviderEvent,
    ProviderEventStatus,
)
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.authorization import (
    AuthorizationSubject,
    Permission,
    RBACAuthorizer,
)
from shema_platform.foundation.errors import AuthorizationError, IdempotencyConflict
from shema_platform.foundation.idempotency import IdempotencyStore
from shema_platform.foundation.outbox import OutboxStore
from shema_platform.foundation.policy import PolicyEngine


@dataclass
class MemoryOrders:
    orders: dict[str, Order] = field(default_factory=dict)

    def get(self, order_id: str) -> Order | None:
        return self.orders.get(order_id)

    def add(self, order: Order) -> None:
        self.orders[order.order_id] = order


@dataclass
class MemoryPayments:
    payments: dict[str, PaymentIntent] = field(default_factory=dict)

    def add(self, payment: PaymentIntent) -> None:
        self.payments[payment.payment_id] = payment

    def get(self, payment_id: str) -> PaymentIntent | None:
        return self.payments.get(payment_id)

    def save(self, payment: PaymentIntent) -> None:
        self.payments[payment.payment_id] = payment


@dataclass
class MemoryAttempts:
    attempts: dict[str, PaymentAttempt] = field(default_factory=dict)

    def add(self, attempt: PaymentAttempt) -> None:
        self.attempts[attempt.attempt_id] = attempt

    def get(self, attempt_id: str) -> PaymentAttempt | None:
        return self.attempts.get(attempt_id)

    def find_by_provider_ref(self, provider_ref: str) -> PaymentAttempt | None:
        return next(
            (
                attempt
                for attempt in self.attempts.values()
                if attempt.provider_ref == provider_ref
            ),
            None,
        )

    def claim_for_send(
        self,
        attempt_id: str,
        worker_id: str,
        *,
        lease_until: datetime,
        now: datetime,
    ) -> PaymentAttempt:
        current = self.attempts[attempt_id]
        if current.status is PaymentAttemptStatus.SENDING and (
            current.lease_until is None or current.lease_until > now
        ):
            raise RuntimeError("active payment attempt lease")
        if current.status not in {
            PaymentAttemptStatus.READY,
            PaymentAttemptStatus.SENDING,
        }:
            raise RuntimeError("payment attempt is not claimable")
        claimed = current.reserve(worker_id, lease_until)
        self.attempts[attempt_id] = claimed
        return claimed

    def complete(
        self,
        attempt_id: str,
        worker_id: str,
        *,
        status: PaymentAttemptStatus,
        provider_ref: str | None,
        now: datetime,
    ) -> PaymentAttempt:
        current = self.attempts[attempt_id]
        if (
            current.status is not PaymentAttemptStatus.SENDING
            or current.worker_id != worker_id
            or current.lease_until is None
            or current.lease_until <= now
        ):
            raise RuntimeError("current payment lease required")
        completed = PaymentAttempt(
            attempt_id=current.attempt_id,
            payment_id=current.payment_id,
            attempt_number=current.attempt_number,
            external_idempotency_key=current.external_idempotency_key,
            status=status,
            provider_ref=provider_ref or current.provider_ref,
        )
        self.attempts[attempt_id] = completed
        return completed

    def apply_provider_result(
        self,
        attempt_id: str,
        *,
        status: PaymentAttemptStatus,
        provider_ref: str | None,
    ) -> PaymentAttempt:
        current = self.attempts[attempt_id]
        if current.status in {
            PaymentAttemptStatus.SUCCEEDED,
            PaymentAttemptStatus.FAILED,
            PaymentAttemptStatus.EXPIRED,
        }:
            return current
        completed = PaymentAttempt(
            attempt_id=current.attempt_id,
            payment_id=current.payment_id,
            attempt_number=current.attempt_number,
            external_idempotency_key=current.external_idempotency_key,
            status=status,
            provider_ref=provider_ref or current.provider_ref,
        )
        self.attempts[attempt_id] = completed
        return completed


@dataclass
class MemoryProviderEvents:
    events: dict[str, ProviderEvent] = field(default_factory=dict)

    def add(self, event: ProviderEvent) -> None:
        existing = self.events.get(event.event_id)
        if existing is not None:
            return
        self.events[event.event_id] = event

    def get(self, event_id: str) -> ProviderEvent | None:
        return self.events.get(event_id)

    def mark_processed(
        self,
        event_id: str,
        *,
        status: ProviderEventStatus,
        processed_at: datetime,
    ) -> ProviderEvent:
        event = self.events[event_id]
        if event.status is status:
            return event
        updated = (
            event.processed()
            if status is ProviderEventStatus.PROCESSED
            else event.ignored()
        )
        self.events[event_id] = updated
        return updated


@dataclass
class MemoryEconomics:
    entries: list[EconomicEntry] = field(default_factory=list)

    def add(self, entry: EconomicEntry) -> None:
        self.entries.append(entry)

    def list_for_entity(self, entity_ref: str) -> tuple[EconomicEntry, ...]:
        return tuple(
            entry for entry in self.entries if entry.entity_ref == entity_ref
        )


@dataclass
class MemoryAudit:
    records: list[AuditRecord] = field(default_factory=list)

    def append(self, record: AuditRecord) -> None:
        self.records.append(record)


@dataclass
class MemoryUow:
    orders: MemoryOrders
    payments: MemoryPayments
    payment_attempts: MemoryAttempts
    provider_events: MemoryProviderEvents
    economics: MemoryEconomics
    idempotency: IdempotencyStore = field(default_factory=IdempotencyStore)
    outbox: OutboxStore = field(default_factory=OutboxStore)
    audits: MemoryAudit = field(default_factory=MemoryAudit)

    def __enter__(self) -> MemoryUow:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        return False


@dataclass
class FakePaymentAdapter(PaymentProviderAdapter):
    provider_name: str = "fake"
    calls: list[str] = field(default_factory=list)
    result: PaymentProviderResult = field(
        default_factory=lambda: PaymentProviderResult(
            provider_ref="provider-payment-1",
            status=PaymentAttemptStatus.SUCCEEDED,
            amount=Money(3000, "RUB"),
        )
    )
    webhook: VerifiedPaymentEvent | None = None

    def create_payment(
        self,
        payment: PaymentIntent,
        attempt: PaymentAttempt,
    ) -> PaymentProviderResult:
        self.calls.append(attempt.external_idempotency_key)
        return self.result

    def verify_webhook(
        self,
        *,
        headers: dict[str, str],
        payload: bytes,
    ) -> VerifiedPaymentEvent:
        if self.webhook is None:
            raise RuntimeError("webhook fixture is missing")
        return self.webhook


def make_order(status: OrderStatus = OrderStatus.CONFIRMED) -> Order:
    order = Order(
        order_id="order-1",
        identity_id="identity-1",
        source_action_id="action-1",
        lines=(
            OrderLine(
                line_id="line-1",
                description="Service",
                quantity=Decimal("2"),
                unit_price=Money(1500, "RUB"),
            ),
        ),
    )
    if status is OrderStatus.CONFIRMED:
        return order.confirm()
    return order.confirm().start().complete()


def workflow_parts(
    *,
    order: Order | None = None,
) -> tuple[
    MemoryUow,
    PaymentCreationWorkflow,
    PaymentExecutionWorkflow,
    PaymentWebhookWorkflow,
    FakePaymentAdapter,
]:
    uow = MemoryUow(
        orders=MemoryOrders(),
        payments=MemoryPayments(),
        payment_attempts=MemoryAttempts(),
        provider_events=MemoryProviderEvents(),
        economics=MemoryEconomics(),
    )
    uow.orders.add(order or make_order())
    authorizer = RBACAuthorizer(
        (
            AuthorizationSubject(
                "operator-1",
                frozenset({Permission.PAYMENT_CREATE}),
            ),
        )
    )
    adapter = FakePaymentAdapter()
    gateway = PaymentGateway(adapter)
    creation = PaymentCreationWorkflow(
        lambda: uow,
        authorizer,
        PolicyEngine(),
    )
    execution = PaymentExecutionWorkflow(
        lambda: uow,
        gateway,
        worker_id="payment-worker-1",
    )
    webhook = PaymentWebhookWorkflow(lambda: uow, gateway)
    return uow, creation, execution, webhook, adapter


def test_payment_creation_uses_order_total_and_idempotency() -> None:
    uow, creation, _, _, _ = workflow_parts()

    actor = Actor("operator-1", trust_level=2)
    first = creation.create(
        actor=actor,
        order_id="order-1",
        idempotency_key="payment-key-1",
    )
    second = creation.create(
        actor=actor,
        order_id="order-1",
        idempotency_key="payment-key-1",
    )

    assert first == second
    assert first.amount == "3000.00"
    payment = uow.payments.get(first.payment_id)
    assert payment is not None
    assert payment.status is PaymentIntentStatus.PENDING


def test_payment_creation_is_authorized() -> None:
    uow, creation, _, _, _ = workflow_parts()
    del uow

    with pytest.raises(AuthorizationError, match="permission denied"):
        creation.create(
            actor=Actor("operator-2", trust_level=2),
            order_id="order-1",
            idempotency_key="payment-key-2",
        )


def test_payment_creation_rejects_idempotency_reuse_for_different_order() -> None:
    uow, creation, _, _, _ = workflow_parts()
    actor = Actor("operator-1", trust_level=2)
    creation.create(
        actor=actor,
        order_id="order-1",
        idempotency_key="payment-key-1",
    )
    uow.orders.add(
        Order(
            order_id="order-2",
            identity_id="identity-2",
            source_action_id="action-2",
            lines=(OrderLine("line-2", "Other", Decimal("1"), Money(100, "RUB")),),
            status=OrderStatus.CONFIRMED,
        )
    )

    with pytest.raises(IdempotencyConflict):
        creation.create(
            actor=actor,
            order_id="order-2",
            idempotency_key="payment-key-1",
        )


def test_payment_execution_calls_provider_once_and_records_revenue() -> None:
    uow, creation, execution, _, adapter = workflow_parts()
    created = creation.create(
        actor=Actor("operator-1", trust_level=2),
        order_id="order-1",
        idempotency_key="payment-key-1",
    )

    attempt_id = next(iter(uow.payment_attempts.attempts))
    result = execution.execute(
        payment_id=created.payment_id,
        attempt_id=attempt_id,
    )
    assert result is PaymentExecutionState.SUCCEEDED
    assert len(adapter.calls) == 1

    payment = uow.payments.get(created.payment_id)
    assert payment is not None
    assert payment.status is PaymentIntentStatus.SUCCEEDED
    revenues = [
        entry for entry in uow.economics.entries
        if entry.kind is EconomicKind.REVENUE
    ]
    assert len(revenues) == 1
    assert revenues[0].amount == Money(3000, "RUB")


def test_payment_webhook_finishes_pending_payment_once_and_records_revenue() -> None:
    uow, creation, _, webhook, adapter = workflow_parts()
    created = creation.create(
        actor=Actor("operator-1", trust_level=2),
        order_id="order-1",
        idempotency_key="payment-key-2",
    )
    attempt_id = next(iter(uow.payment_attempts.attempts))
    uow.payment_attempts.apply_provider_result(
        attempt_id,
        status=PaymentAttemptStatus.PENDING,
        provider_ref="provider-payment-2",
    )

    now = datetime.now(UTC)
    event = ProviderEvent(
        event_id="provider-event-1",
        provider_ref="provider-payment-2",
        event_type="payment.succeeded",
        signature_verified=True,
        payload_hash="sha256:event-1",
        received_at=now,
    )
    adapter.webhook = VerifiedPaymentEvent(
        event=event,
        payment_status=PaymentAttemptStatus.SUCCEEDED,
        amount=Money(3000, "RUB"),
    )

    first = webhook.process(headers={}, payload=b"payload")
    second = webhook.process(headers={}, payload=b"payload")

    assert first.status == "succeeded"
    assert first.payment_id == created.payment_id
    assert second.status == "duplicate"

    payment = uow.payments.get(created.payment_id)
    assert payment is not None
    assert payment.status is PaymentIntentStatus.SUCCEEDED
    revenues = [
        entry for entry in uow.economics.entries
        if entry.kind is EconomicKind.REVENUE
    ]
    assert len(revenues) == 1
    assert uow.provider_events.get(event.event_id) is not None
    assert uow.provider_events.get(event.event_id).status is ProviderEventStatus.PROCESSED


def test_payment_provider_failure_does_not_create_revenue() -> None:
    uow, creation, execution, _, adapter = workflow_parts()
    adapter.result = PaymentProviderResult(
        provider_ref="provider-payment-fail",
        status=PaymentAttemptStatus.FAILED,
    )
    created = creation.create(
        actor=Actor("operator-1", trust_level=2),
        order_id="order-1",
        idempotency_key="payment-key-3",
    )
    attempt_id = next(iter(uow.payment_attempts.attempts))

    result = execution.execute(
        payment_id=created.payment_id,
        attempt_id=attempt_id,
    )

    assert result is PaymentExecutionState.FAILED
    payment = uow.payments.get(created.payment_id)
    assert payment is not None
    assert payment.status is PaymentIntentStatus.FAILED
    assert [
        entry for entry in uow.economics.entries
        if entry.kind is EconomicKind.REVENUE
    ] == []


def test_payment_retry_reuses_stable_external_effect_key() -> None:
    uow, creation, execution, _, adapter = workflow_parts()
    created = creation.create(
        actor=Actor("operator-1", trust_level=2),
        order_id="order-1",
        idempotency_key="payment-key-4",
    )
    attempt_id = next(iter(uow.payment_attempts.attempts))

    before = uow.payment_attempts.get(attempt_id)
    assert before is not None
    first_key = before.external_idempotency_key

    execution.execute(payment_id=created.payment_id, attempt_id=attempt_id)

    assert adapter.calls == [first_key]
    assert adapter.calls.count(first_key) == 1


def test_payment_gateway_rejects_provider_amount_mismatch() -> None:
    adapter = FakePaymentAdapter(
        result=PaymentProviderResult(
            provider_ref="provider-payment-1",
            status=PaymentAttemptStatus.SUCCEEDED,
            amount=Money(2999, "RUB"),
        )
    )
    gateway = PaymentGateway(adapter)
    payment = PaymentIntent(
        payment_id="payment-1",
        order_id="order-1",
        amount=Money(3000, "RUB"),
        idempotency_key="key-1",
    ).begin()
    attempt = PaymentAttempt(
        attempt_id="attempt-1",
        payment_id="payment-1",
        attempt_number=1,
        external_idempotency_key="external-1",
        status=PaymentAttemptStatus.SENDING,
        worker_id="worker-1",
        lease_until=datetime.now(UTC) + timedelta(minutes=5),
    )

    with pytest.raises(Exception, match="amount"):
        gateway.create_payment(payment, attempt)

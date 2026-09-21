from datetime import UTC, datetime, timedelta

import pytest

from shema_platform.domain.money import Money
from shema_platform.domain.payment import (
    PaymentAttempt,
    PaymentAttemptStatus,
    PaymentIntent,
    PaymentIntentStatus,
    ProviderEvent,
    ProviderEventStatus,
)
from shema_platform.domain.settlement import (
    ReconciliationItem,
    ReconciliationStatus,
    SettlementLine,
    SettlementRecord,
    SettlementStatement,
    SettlementStatus,
)


def test_payment_intent_lifecycle() -> None:
    payment = PaymentIntent(
        payment_id="payment-1",
        order_id="order-1",
        amount=Money("6000.00", "RUB"),
        idempotency_key="pay-key-1",
    )

    pending = payment.begin()
    processing = pending.mark_processing()
    succeeded = processing.succeed()

    assert pending.status is PaymentIntentStatus.PENDING
    assert processing.status is PaymentIntentStatus.PROCESSING
    assert succeeded.status is PaymentIntentStatus.SUCCEEDED


def test_payment_intent_rejects_client_side_success_from_draft() -> None:
    payment = PaymentIntent(
        payment_id="payment-1",
        order_id="order-1",
        amount=Money(6000, "RUB"),
        idempotency_key="pay-key-1",
    )

    with pytest.raises(ValueError):
        payment.succeed()


def test_payment_attempt_requires_lease_for_external_effect() -> None:
    attempt = PaymentAttempt(
        attempt_id="attempt-1",
        payment_id="payment-1",
        attempt_number=1,
        external_idempotency_key="provider-key-1",
    )
    reserved = attempt.reserve(
        worker_id="payment-worker-1",
        lease_until=datetime.now(UTC) + timedelta(minutes=5),
    )
    completed = reserved.succeed(provider_ref="provider-payment-1")

    assert reserved.status is PaymentAttemptStatus.SENDING
    assert completed.status is PaymentAttemptStatus.SUCCEEDED
    assert completed.provider_ref == "provider-payment-1"


def test_provider_event_requires_verified_signature() -> None:
    with pytest.raises(ValueError, match="signature"):
        ProviderEvent(
            event_id="event-1",
            provider_ref="provider-payment-1",
            event_type="payment.succeeded",
            signature_verified=False,
            payload_hash="sha256:test",
            received_at=datetime.now(UTC),
        )


def test_provider_event_processing_is_idempotent_by_state() -> None:
    event = ProviderEvent(
        event_id="event-1",
        provider_ref="provider-payment-1",
        event_type="payment.succeeded",
        signature_verified=True,
        payload_hash="sha256:test",
        received_at=datetime.now(UTC),
    )

    processed = event.processed()

    assert processed.status is ProviderEventStatus.PROCESSED
    with pytest.raises(ValueError):
        processed.processed()


def test_settlement_amounts_are_deterministic() -> None:
    settlement = SettlementRecord(
        settlement_id="settlement-1",
        provider_settlement_ref="provider-settlement-1",
        statement_hash="sha256:statement-1",
        gross=Money("6000.00", "RUB"),
        fees=Money("150.00", "RUB"),
        net=Money("5850.00", "RUB"),
        settled_at=datetime.now(UTC),
    )

    reconciling = settlement.begin_reconciliation()
    settled = reconciling.settle()

    assert settled.status is SettlementStatus.SETTLED


def test_settlement_rejects_incorrect_net() -> None:
    with pytest.raises(ValueError, match="gross minus fees"):
        SettlementRecord(
            settlement_id="settlement-1",
            provider_settlement_ref="provider-settlement-1",
            statement_hash="sha256:statement-1",
            gross=Money(6000, "RUB"),
            fees=Money(150, "RUB"),
            net=Money(5800, "RUB"),
            settled_at=datetime.now(UTC),
        )


def test_reconciliation_is_durable_review_state_until_resolved() -> None:
    item = ReconciliationItem(
        reconciliation_id="recon-1",
        settlement_id="settlement-1",
        reason_code="amount_mismatch",
        expected_amount=Money(6000, "RUB"),
        observed_amount=Money(5900, "RUB"),
        currency="RUB",
        created_at=datetime.now(UTC),
    )

    assert item.status is ReconciliationStatus.OPEN
    resolved = item.resolve(datetime.now(UTC) + timedelta(minutes=1))
    assert resolved.status is ReconciliationStatus.RESOLVED


def test_statement_requires_line_total_and_net_math() -> None:
    now = datetime.now(UTC)
    statement = SettlementStatement(
        statement_id="statement-1",
        provider_settlement_ref="provider-settlement-1",
        statement_hash="sha256:statement-1",
        lines=(
            SettlementLine(
                line_id="line-1",
                settlement_id="settlement-1",
                provider_ref="provider-payment-1",
                amount=Money(6000, "RUB"),
                statement_ref="statement-1",
            ),
        ),
        gross=Money(6000, "RUB"),
        fees=Money(150, "RUB"),
        net=Money(5850, "RUB"),
        settled_at=now,
    )

    assert statement.lines[0].settlement_id == "settlement-1"


def test_discrepancy_must_be_explicitly_resolved() -> None:
    settlement = SettlementRecord(
        settlement_id="settlement-1",
        provider_settlement_ref="provider-settlement-1",
        statement_hash="sha256:statement-1",
        gross=Money(6000, "RUB"),
        fees=Money(150, "RUB"),
        net=Money(5850, "RUB"),
        settled_at=datetime.now(UTC),
    )

    discrepancy = settlement.begin_reconciliation().mark_discrepancy()
    resolved = discrepancy.resolve_discrepancy()

    assert resolved.status is SettlementStatus.SETTLED

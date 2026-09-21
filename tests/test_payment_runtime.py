from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from shema_platform.application.payment_execution import (
    PaymentProviderAdapter,
    PaymentProviderResult,
    VerifiedPaymentEvent,
)
from shema_platform.application.settlement_execution import (
    SettlementProviderAdapter,
)
from shema_platform.domain.money import Money
from shema_platform.domain.payment import (
    PaymentAttempt,
    PaymentAttemptStatus,
    PaymentIntent,
    ProviderEvent,
)
from shema_platform.domain.settlement import SettlementStatement
from shema_platform.foundation.authorization import (
    AuthorizationSubject,
    Permission,
    RBACAuthorizer,
)
from shema_platform.foundation.policy import PolicyEngine
from shema_platform.runtime.payment import build_payment_runtime
from shema_platform.runtime.providers import ProviderNotConfigured, ProviderRegistry


@dataclass
class FakePaymentAdapter(PaymentProviderAdapter):
    provider_name: str = "test-payment"

    def create_payment(
        self,
        payment: PaymentIntent,
        attempt: PaymentAttempt,
    ) -> PaymentProviderResult:
        return PaymentProviderResult(
            provider_ref="provider-payment-1",
            status=PaymentAttemptStatus.SUCCEEDED,
            amount=payment.amount,
        )

    def verify_webhook(
        self,
        *,
        headers: dict[str, str],
        payload: bytes,
    ) -> VerifiedPaymentEvent:
        event = ProviderEvent(
            event_id="event-1",
            provider_ref="provider-payment-1",
            event_type="payment.succeeded",
            signature_verified=True,
            payload_hash="sha256:test",
            received_at=datetime.now(UTC),
        )
        return VerifiedPaymentEvent(
            event=event,
            amount=Money("3000", "RUB"),
            source_payment_ref="provider-payment-1",
            payment_status=PaymentAttemptStatus.SUCCEEDED,
        )


@dataclass
class FakeSettlementAdapter(SettlementProviderAdapter):
    provider_name: str = "test-settlement"

    def verify_settlement_statement(
        self,
        *,
        headers: dict[str, str],
        payload: bytes,
    ) -> SettlementStatement:
        raise AssertionError("test adapter should not be called during composition")


def test_provider_registry_fails_closed() -> None:
    registry = ProviderRegistry[FakePaymentAdapter]({"test": FakePaymentAdapter()})
    assert registry.get("test").provider_name == "test-payment"

    with pytest.raises(ProviderNotConfigured, match="not configured"):
        registry.require_for_production("missing")


def test_payment_runtime_binds_real_execution_and_webhook_workflows() -> None:
    authorizer = RBACAuthorizer(
        (
            AuthorizationSubject(
                "operator-1",
                frozenset({Permission.PAYMENT_CREATE}),
            ),
        )
    )
    payment_registry = ProviderRegistry[PaymentProviderAdapter](
        {"test-payment": FakePaymentAdapter()}
    )
    settlement_registry = ProviderRegistry[SettlementProviderAdapter](
        {"test-settlement": FakeSettlementAdapter()}
    )

    runtime = build_payment_runtime(
        unit_of_work_factory=lambda: None,
        payment_providers=payment_registry,
        settlement_providers=settlement_registry,
        payment_provider_name="test-payment",
        settlement_provider_name="test-settlement",
        authorizer=authorizer,
        policy=PolicyEngine(),
        worker_id="payment-worker",
    )

    assert runtime.execution is not None
    assert runtime.webhook is not None
    assert runtime.settlement is not None
    assert runtime.settlement_verifier is not None
    assert runtime.outbox_router is not None
    assert "payment.create_requested" in runtime.outbox_router.handlers


def test_payment_runtime_rejects_missing_production_provider() -> None:
    registry = ProviderRegistry[PaymentProviderAdapter](
        {"test-payment": FakePaymentAdapter()}
    )
    settlement_registry = ProviderRegistry[SettlementProviderAdapter](
        {"test-settlement": FakeSettlementAdapter()}
    )

    with pytest.raises(ProviderNotConfigured):
        build_payment_runtime(
            unit_of_work_factory=lambda: None,
            payment_providers=registry,
            settlement_providers=settlement_registry,
            payment_provider_name="missing",
            settlement_provider_name="test-settlement",
            authorizer=RBACAuthorizer(()),
            policy=PolicyEngine(),
            worker_id="payment-worker",
        )

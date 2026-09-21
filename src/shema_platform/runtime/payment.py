from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from shema_platform.application.outbox_router import OutboxHandlerRouter
from shema_platform.application.payment_execution import (
    PaymentCreationWorkflow,
    PaymentExecutionWorkflow,
    PaymentGateway,
    PaymentProviderAdapter,
    PaymentWebhookWorkflow,
)
from shema_platform.application.ports import UnitOfWork
from shema_platform.application.settlement_execution import (
    SettlementProviderAdapter,
    SettlementStatementVerifier,
    SettlementWorkflow,
)
from shema_platform.runtime.outbox import build_outbox_router
from shema_platform.runtime.providers import ProviderRegistry


@dataclass(frozen=True, slots=True)
class PaymentRuntime:
    creation: PaymentCreationWorkflow
    execution: PaymentExecutionWorkflow
    webhook: PaymentWebhookWorkflow
    settlement: SettlementWorkflow
    settlement_verifier: SettlementStatementVerifier
    payment_providers: ProviderRegistry[PaymentProviderAdapter]
    settlement_providers: ProviderRegistry[SettlementProviderAdapter]
    outbox_router: OutboxHandlerRouter


def build_payment_runtime(
    *,
    unit_of_work_factory: Callable[[], UnitOfWork],
    payment_providers: ProviderRegistry[PaymentProviderAdapter],
    settlement_providers: ProviderRegistry[SettlementProviderAdapter],
    payment_provider_name: str,
    settlement_provider_name: str,
    authorizer,
    policy,
    worker_id: str,
) -> PaymentRuntime:
    payment_adapter = payment_providers.require_for_production(
        payment_provider_name
    )
    settlement_adapter = settlement_providers.require_for_production(
        settlement_provider_name
    )

    gateway = PaymentGateway(payment_adapter)
    creation = PaymentCreationWorkflow(
        unit_of_work_factory,
        authorizer,
        policy,
    )
    execution = PaymentExecutionWorkflow(
        unit_of_work_factory,
        gateway,
        worker_id=worker_id,
    )
    webhook = PaymentWebhookWorkflow(
        unit_of_work_factory,
        gateway,
    )
    settlement = SettlementWorkflow(unit_of_work_factory)
    settlement_verifier = SettlementStatementVerifier(settlement_adapter)
    outbox_router = build_outbox_router(execution)

    return PaymentRuntime(
        creation=creation,
        execution=execution,
        webhook=webhook,
        settlement=settlement,
        settlement_verifier=settlement_verifier,
        payment_providers=payment_providers,
        settlement_providers=settlement_providers,
        outbox_router=outbox_router,
    )

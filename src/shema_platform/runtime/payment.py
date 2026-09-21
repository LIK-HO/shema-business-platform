from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

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
    SettlementWorkflow,
    SettlementStatementVerifier,
)
from shema_platform.runtime.providers import ProviderRegistry


@dataclass(frozen=True, slots=True)
class PaymentRuntime:
    creation: PaymentCreationWorkflow
    execution: PaymentExecutionWorkflow
    webhook: PaymentWebhookWorkflow
    settlement: SettlementWorkflow
    payment_providers: ProviderRegistry[PaymentProviderAdapter]
    settlement_providers: ProviderRegistry[SettlementProviderAdapter]


def build_payment_runtime(
    *,
    unit_of_work_factory: Callable[[], UnitOfWork],
    payment_providers: ProviderRegistry[PaymentProviderAdapter],
    settlement_providers: ProviderRegistry[SettlementProviderAdapter],
    authorizer,
    policy,
    worker_id: str,
) -> PaymentRuntime:
    creation = PaymentCreationWorkflow(
        unit_of_work_factory,
        authorizer,
        policy,
    )
    settlement = SettlementWorkflow(unit_of_work_factory)
    return PaymentRuntime(
        creation=creation,
        execution=None,
        webhook=None,
        settlement=settlement,
        payment_providers=payment_providers,
        settlement_providers=settlement_providers,
    )

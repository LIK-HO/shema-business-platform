from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from shema_platform.application.ports import UnitOfWork
from shema_platform.domain.money import Money
from shema_platform.domain.payment import PaymentAttemptStatus, PaymentIntentStatus
from shema_platform.domain.settlement import (
    ReconciliationItem,
    ReconciliationStatus,
    SettlementLine,
    SettlementRecord,
    SettlementStatement,
    SettlementStatus,
)
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.errors import IntegrityViolation
from shema_platform.foundation.outbox import OutboxEvent, utc_now


class SettlementProviderAdapter(Protocol):
    """Provider-specific statement verification behind a stable settlement port."""

    provider_name: str

    def verify_settlement_statement(
        self,
        *,
        headers: Mapping[str, str],
        payload: bytes,
    ) -> SettlementStatement: ...


@dataclass(frozen=True, slots=True)
class SettlementReconciliationResult:
    settlement_id: str
    status: SettlementStatus
    discrepancies: tuple[str, ...]


class SettlementWorkflow:
    """Ingests immutable settlement statements and deterministically reconciles lines."""

    def __init__(
        self,
        unit_of_work_factory: Callable[[], UnitOfWork],
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    @staticmethod
    def settlement_id(provider_settlement_ref: str) -> str:
        return str(
            uuid5(
                NAMESPACE_URL,
                f"settlement:{provider_settlement_ref}",
            )
        )

    @staticmethod
    def reconciliation_id(
        settlement_id: str,
        provider_ref: str,
        reason_code: str,
    ) -> str:
        return str(
            uuid5(
                NAMESPACE_URL,
                f"reconciliation:{settlement_id}:{provider_ref}:{reason_code}",
            )
        )

    def ingest(
        self,
        statement: SettlementStatement,
    ) -> SettlementReconciliationResult:
        settlement_id = self.settlement_id(statement.provider_settlement_ref)
        discrepancies: list[str] = []

        with self._unit_of_work_factory() as uow:
            existing = uow.settlements.get(settlement_id)
            if existing is not None:
                if (
                    existing.provider_settlement_ref
                    != statement.provider_settlement_ref
                    or existing.statement_hash != statement.statement_hash
                    or existing.gross != statement.gross
                    or existing.fees != statement.fees
                    or existing.net != statement.net
                    or existing.settled_at != statement.settled_at
                ):
                    raise IntegrityViolation(
                        "provider settlement reference already exists with different immutable facts"
                    )
                return SettlementReconciliationResult(
                    settlement_id=settlement_id,
                    status=existing.status,
                    discrepancies=tuple(
                        item.reconciliation_id
                        for item in uow.reconciliations.list_open_for_settlement(
                            settlement_id
                        )
                    ),
                )

            settlement = SettlementRecord(
                settlement_id=settlement_id,
                provider_settlement_ref=statement.provider_settlement_ref,
                statement_hash=statement.statement_hash,
                gross=statement.gross,
                fees=statement.fees,
                net=statement.net,
                settled_at=statement.settled_at,
            ).begin_reconciliation()

            uow.settlements.add(settlement)

            for line in statement.lines:
                line_record = SettlementLine(
                    line_id=line.line_id,
                    settlement_id=settlement_id,
                    provider_ref=line.provider_ref,
                    amount=line.amount,
                    statement_ref=line.statement_ref,
                )
                uow.settlements.add_line(line_record)

                attempt = uow.payment_attempts.find_by_provider_ref(
                    line.provider_ref
                )
                reason: str | None = None
                expected_amount: Money | None = None
                observed_amount = line.amount

                if attempt is None:
                    reason = "provider_payment_unmatched"
                else:
                    payment = uow.payments.get(attempt.payment_id)
                    if payment is None:
                        reason = "payment_missing"
                    elif payment.status is not PaymentIntentStatus.SUCCEEDED:
                        reason = "payment_not_succeeded"
                    else:
                        expected_amount = payment.amount
                        if payment.amount != line.amount:
                            reason = "payment_amount_mismatch"

                if reason is not None:
                    reconciliation_id = self.reconciliation_id(
                        settlement_id,
                        line.provider_ref,
                        reason,
                    )
                    uow.reconciliations.add(
                        ReconciliationItem(
                            reconciliation_id=reconciliation_id,
                            settlement_id=settlement_id,
                            reason_code=reason,
                            expected_amount=expected_amount,
                            observed_amount=observed_amount,
                            currency=line.amount.currency,
                            status=ReconciliationStatus.OPEN,
                            created_at=utc_now(),
                        )
                    )
                    discrepancies.append(reconciliation_id)

            if discrepancies:
                settlement = settlement.mark_discrepancy()
            else:
                settlement = settlement.settle()

            uow.settlements.save(settlement)
            uow.audits.append(
                AuditRecord(
                    audit_id=str(
                        uuid5(
                            NAMESPACE_URL,
                            f"audit:settlement.ingest:{settlement_id}",
                        )
                    ),
                    actor_id="settlement-provider",
                    action="settlement.ingested",
                    resource_type="settlement",
                    resource_id=settlement_id,
                    outcome=(
                        "discrepancy" if discrepancies else "settled"
                    ),
                    occurred_at=utc_now(),
                    metadata={
                        "provider_settlement_ref": statement.provider_settlement_ref,
                        "statement_hash": statement.statement_hash,
                        "line_count": len(statement.lines),
                        "discrepancy_count": len(discrepancies),
                    },
                )
            )
            uow.outbox.append(
                OutboxEvent(
                    event_id=str(
                        uuid5(
                            NAMESPACE_URL,
                            f"settlement.ingested:{settlement_id}",
                        )
                    ),
                    event_type=(
                        "settlement.discrepancy"
                        if discrepancies
                        else "settlement.settled"
                    ),
                    aggregate_type="settlement",
                    aggregate_id=settlement_id,
                    payload={
                        "provider_settlement_ref": statement.provider_settlement_ref,
                        "status": settlement.status.value,
                        "discrepancies": discrepancies,
                    },
                    occurred_at=utc_now(),
                )
            )

            return SettlementReconciliationResult(
                settlement_id=settlement_id,
                status=settlement.status,
                discrepancies=tuple(discrepancies),
            )

    def resolve(
        self,
        settlement_id: str,
    ) -> SettlementReconciliationResult:
        with self._unit_of_work_factory() as uow:
            settlement = uow.settlements.get(settlement_id)
            if settlement is None:
                raise KeyError(f"unknown settlement: {settlement_id}")

            open_items = uow.reconciliations.list_open_for_settlement(
                settlement_id
            )
            if open_items:
                raise IntegrityViolation(
                    "settlement cannot be closed while reconciliation discrepancies remain"
                )

            if settlement.status is SettlementStatus.DISCREPANCY:
                settlement = settlement.resolve_discrepancy()
                uow.settlements.save(settlement)

            uow.audits.append(
                AuditRecord(
                    audit_id=str(
                        uuid5(
                            NAMESPACE_URL,
                            f"audit:settlement.resolved:{settlement_id}",
                        )
                    ),
                    actor_id="settlement-operator",
                    action="settlement.resolved",
                    resource_type="settlement",
                    resource_id=settlement_id,
                    outcome="settled",
                    occurred_at=utc_now(),
                    metadata={},
                )
            )

            return SettlementReconciliationResult(
                settlement_id=settlement_id,
                status=settlement.status,
                discrepancies=(),
            )

    def resolve_item(
        self,
        item: ReconciliationItem,
        resolved_at,
    ) -> ReconciliationItem:
        if item.status is not ReconciliationStatus.RESOLVED:
            raise ValueError("resolve_item requires an already-resolved domain item")
        with self._unit_of_work_factory() as uow:
            return uow.reconciliations.resolve(item)


class SettlementStatementVerifier:
    """Provider-neutral verifier facade; concrete cryptographic verification stays in adapter."""

    def __init__(self, adapter: SettlementProviderAdapter) -> None:
        self._adapter = adapter

    def verify(
        self,
        *,
        headers: Mapping[str, str],
        payload: bytes,
    ) -> SettlementStatement:
        statement = self._adapter.verify_settlement_statement(
            headers=headers,
            payload=payload,
        )
        if not statement.statement_hash:
            raise IntegrityViolation("settlement statement has no hash")
        return statement


def statement_hash(payload: bytes) -> str:
    """Canonical transport hash for audit/idempotence evidence."""

    return sha256(payload).hexdigest()

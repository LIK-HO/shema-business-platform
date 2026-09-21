from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from shema_platform.domain.money import Money


class SettlementStatus(StrEnum):
    EXPECTED = "expected"
    RECONCILING = "reconciling"
    SETTLED = "settled"
    DISCREPANCY = "discrepancy"


class ReconciliationStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


@dataclass(frozen=True, slots=True)
class SettlementRecord:
    settlement_id: str
    provider_settlement_ref: str
    gross: Money
    fees: Money
    net: Money
    settled_at: datetime
    status: SettlementStatus = SettlementStatus.EXPECTED

    def __post_init__(self) -> None:
        if not self.settlement_id.strip() or not self.provider_settlement_ref.strip():
            raise ValueError("settlement identifiers are required")
        if self.gross.amount < 0 or self.fees.amount < 0 or self.net.amount < 0:
            raise ValueError("settlement amounts cannot be negative")
        if self.gross.currency != self.fees.currency or self.gross.currency != self.net.currency:
            raise ValueError("settlement currencies must match")
        if self.settled_at.tzinfo is None:
            raise ValueError("settled_at must be timezone-aware")
        if self.net.amount != self.gross.amount.subtract(self.fees.amount):
            raise ValueError("settlement net must equal gross minus fees")

    def begin_reconciliation(self) -> SettlementRecord:
        if self.status is not SettlementStatus.EXPECTED:
            raise ValueError("only expected settlement can enter reconciliation")
        return self._with_status(SettlementStatus.RECONCILING)

    def settle(self) -> SettlementRecord:
        if self.status is not SettlementStatus.RECONCILING:
            raise ValueError("only reconciling settlement can settle")
        return self._with_status(SettlementStatus.SETTLED)

    def mark_discrepancy(self) -> SettlementRecord:
        if self.status is not SettlementStatus.RECONCILING:
            raise ValueError("only reconciling settlement can become discrepancy")
        return self._with_status(SettlementStatus.DISCREPANCY)

    def resolve_discrepancy(self) -> SettlementRecord:
        if self.status is not SettlementStatus.DISCREPANCY:
            raise ValueError("only discrepancy settlement can be resolved")
        return self._with_status(SettlementStatus.SETTLED)

    def _with_status(self, status: SettlementStatus) -> SettlementRecord:
        return SettlementRecord(
            settlement_id=self.settlement_id,
            provider_settlement_ref=self.provider_settlement_ref,
            gross=self.gross,
            fees=self.fees,
            net=self.net,
            settled_at=self.settled_at,
            status=status,
        )


@dataclass(frozen=True, slots=True)
class ReconciliationItem:
    reconciliation_id: str
    settlement_id: str
    reason_code: str
    expected_amount: Money | None
    observed_amount: Money | None
    currency: str
    status: ReconciliationStatus = ReconciliationStatus.OPEN
    created_at: datetime | None = None
    resolved_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.reconciliation_id.strip() or not self.settlement_id.strip():
            raise ValueError("reconciliation identifiers are required")
        if not self.reason_code.strip():
            raise ValueError("reason_code is required")
        if len(self.currency.strip()) != 3:
            raise ValueError("currency must be a 3-letter code")
        if self.expected_amount is not None and self.expected_amount.currency != self.currency:
            raise ValueError("expected amount currency mismatch")
        if self.observed_amount is not None and self.observed_amount.currency != self.currency:
            raise ValueError("observed amount currency mismatch")

    def resolve(self, resolved_at: datetime) -> ReconciliationItem:
        if self.status is ReconciliationStatus.RESOLVED:
            raise ValueError("reconciliation item is already resolved")
        if resolved_at.tzinfo is None:
            raise ValueError("resolved_at must be timezone-aware")
        return ReconciliationItem(
            reconciliation_id=self.reconciliation_id,
            settlement_id=self.settlement_id,
            reason_code=self.reason_code,
            expected_amount=self.expected_amount,
            observed_amount=self.observed_amount,
            currency=self.currency,
            status=ReconciliationStatus.RESOLVED,
            created_at=self.created_at,
            resolved_at=resolved_at,
        )


@dataclass(frozen=True, slots=True)
class SettlementLine:
    line_id: str
    settlement_id: str
    provider_ref: str
    amount: Money
    statement_ref: str

    def __post_init__(self) -> None:
        if (
            not self.line_id.strip()
            or not self.settlement_id.strip()
            or not self.provider_ref.strip()
        ):
            raise ValueError("settlement line identifiers are required")
        if not self.statement_ref.strip():
            raise ValueError("statement_ref is required")
        if self.amount.amount <= 0:
            raise ValueError("settlement line amount must be positive")


@dataclass(frozen=True, slots=True)
class SettlementStatement:
    statement_id: str
    provider_settlement_ref: str
    statement_hash: str
    lines: tuple[SettlementLine, ...]
    gross: Money
    fees: Money
    net: Money
    settled_at: datetime

    def __post_init__(self) -> None:
        if not self.statement_id.strip():
            raise ValueError("statement_id is required")
        if not self.provider_settlement_ref.strip():
            raise ValueError("provider_settlement_ref is required")
        if not self.statement_hash.strip():
            raise ValueError("statement_hash is required")
        if not self.lines:
            raise ValueError("settlement statement must contain lines")
        if self.settled_at.tzinfo is None:
            raise ValueError("settled_at must be timezone-aware")
        if self.gross.currency != self.fees.currency or self.gross.currency != self.net.currency:
            raise ValueError("statement currencies must match")
        line_total = Money(0, self.gross.currency)
        for line in self.lines:
            if line.amount.currency != self.gross.currency:
                raise ValueError("settlement line currency mismatch")
            line_total = line_total.add(line.amount)
        if line_total != self.gross:
            raise ValueError("statement gross must equal settlement line total")
        if self.net != self.gross.subtract(self.fees):
            raise ValueError("statement net must equal gross minus fees")

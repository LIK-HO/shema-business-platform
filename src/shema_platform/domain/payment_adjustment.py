from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from shema_platform.domain.money import Money


class PaymentAdjustmentKind(StrEnum):
    REFUND = "refund"
    REVERSAL = "reversal"
    CHARGEBACK = "chargeback"
    ADJUSTMENT = "adjustment"


@dataclass(frozen=True, slots=True)
class PaymentAdjustment:
    adjustment_id: str
    payment_id: str
    provider_event_id: str
    provider_ref: str
    kind: PaymentAdjustmentKind
    amount: Money
    occurred_at: datetime

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.adjustment_id,
                self.payment_id,
                self.provider_event_id,
                self.provider_ref,
            )
        ):
            raise ValueError("payment adjustment identifiers are required")
        if self.amount.amount <= 0:
            raise ValueError("payment adjustment amount must be positive")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")

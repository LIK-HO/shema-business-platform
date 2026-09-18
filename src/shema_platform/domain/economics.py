from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from shema_platform.domain.money import Money


class EconomicKind(StrEnum):
    PROVIDER_COST = "provider_cost"
    AI_COST = "ai_cost"
    ORDER_COST = "order_cost"
    REVENUE = "revenue"
    ADJUSTMENT = "adjustment"


@dataclass(frozen=True, slots=True)
class EconomicEntry:
    entry_id: str
    entity_ref: str
    kind: EconomicKind
    amount: Money
    source_ref: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        if not self.entry_id.strip() or not self.entity_ref.strip() or not self.source_ref.strip():
            raise ValueError("economic entry references are required")


@dataclass(frozen=True, slots=True)
class EconomicsSummary:
    revenue: Money
    costs: Money

    @property
    def gross_margin(self) -> Money:
        return self.revenue.subtract(self.costs)


class EconomicsService:
    """Calculates economic outcomes only from traceable entries."""

    def summarize(self, entries: tuple[EconomicEntry, ...], currency: str = "RUB") -> EconomicsSummary:
        zero = Money(0, currency)
        revenue = zero
        costs = zero

        for entry in entries:
            if entry.amount.currency != zero.currency:
                raise ValueError("economic entry currency mismatch")
            if entry.kind is EconomicKind.REVENUE:
                revenue = revenue.add(entry.amount)
            else:
                costs = costs.add(entry.amount)

        return EconomicsSummary(revenue=revenue, costs=costs)

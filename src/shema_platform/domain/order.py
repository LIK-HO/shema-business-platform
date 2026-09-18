from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from shema_platform.domain.money import Money


class OrderStatus(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class OrderLine:
    line_id: str
    description: str
    quantity: Decimal
    unit_price: Money

    def __post_init__(self) -> None:
        if not self.line_id.strip() or not self.description.strip():
            raise ValueError("order line identifiers and description are required")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")

    @property
    def total(self) -> Money:
        return self.unit_price.multiply(self.quantity)


@dataclass(frozen=True, slots=True)
class Order:
    order_id: str
    identity_id: str
    source_action_id: str
    lines: tuple[OrderLine, ...]
    status: OrderStatus = OrderStatus.DRAFT

    def __post_init__(self) -> None:
        if not self.order_id.strip():
            raise ValueError("order_id is required")
        if not self.identity_id.strip():
            raise ValueError("identity_id is required")
        if not self.lines:
            raise ValueError("order must contain at least one line")

    @property
    def total(self) -> Money:
        result = self.lines[0].total
        for line in self.lines[1:]:
            result = result.add(line.total)
        return result

    def confirm(self) -> Order:
        if self.status is not OrderStatus.DRAFT:
            raise ValueError("only draft order can be confirmed")
        return Order(
            order_id=self.order_id,
            identity_id=self.identity_id,
            source_action_id=self.source_action_id,
            lines=self.lines,
            status=OrderStatus.CONFIRMED,
        )

    def start(self) -> Order:
        if self.status is not OrderStatus.CONFIRMED:
            raise ValueError("only confirmed order can start")
        return Order(
            order_id=self.order_id,
            identity_id=self.identity_id,
            source_action_id=self.source_action_id,
            lines=self.lines,
            status=OrderStatus.IN_PROGRESS,
        )

    def complete(self) -> Order:
        if self.status is not OrderStatus.IN_PROGRESS:
            raise ValueError("only in-progress order can complete")
        return Order(
            order_id=self.order_id,
            identity_id=self.identity_id,
            source_action_id=self.source_action_id,
            lines=self.lines,
            status=OrderStatus.COMPLETED,
        )

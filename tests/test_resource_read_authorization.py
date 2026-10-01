from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from shema_platform.domain.economics import EconomicEntry, EconomicKind
from shema_platform.domain.money import Money
from shema_platform.domain.order import Order, OrderLine, OrderStatus
from shema_platform.foundation.errors import AuthorizationError
from shema_platform.platform.resource_read_authorization import (
    PostgresResourceReadAuthorizer,
)


class MemoryOrderRepository:
    def __init__(self, orders: tuple[Order, ...]) -> None:
        self.items = {order.order_id: order for order in orders}

    def get(self, order_id: str):
        return self.items.get(order_id)


class MemoryEconomicsRepository:
    def __init__(self, entries: tuple[EconomicEntry, ...]) -> None:
        self.items = entries

    def list_for_entity(self, entity_ref: str):
        return tuple(item for item in self.items if item.entity_ref == entity_ref)


class MemoryUoW:
    def __init__(self, orders: tuple[Order, ...], entries: tuple[EconomicEntry, ...]) -> None:
        self.orders = MemoryOrderRepository(orders)
        self.economics = MemoryEconomicsRepository(entries)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


def order(owner: str) -> Order:
    return Order(
        order_id="order-1",
        identity_id="identity-1",
        source_action_id="action-1",
        owner_actor_id=owner,
        status=OrderStatus.COMPLETED,
        lines=(
            OrderLine(
                line_id="line-1",
                description="Погрузка",
                quantity=Decimal("1"),
                unit_price=Money(1500, "RUB"),
            ),
        ),
    )


def economics() -> EconomicEntry:
    return EconomicEntry(
        entry_id="economics-1",
        entity_ref="order-1",
        kind=EconomicKind.REVENUE,
        amount=Money(1500, "RUB"),
        source_ref="repeat-order:confirm",
        occurred_at=datetime(2026, 9, 29, 9, tzinfo=UTC),
    )


def test_order_read_requires_canonical_owner_scope() -> None:
    authorizer = PostgresResourceReadAuthorizer(
        lambda: MemoryUoW((order("operator-1"),), (economics(),))
    )

    authorizer.require_order_read(order_id="order-1", actor_id="operator-1")

    with pytest.raises(AuthorizationError, match="outside the actor resource scope"):
        authorizer.require_order_read(order_id="order-1", actor_id="operator-2")


def test_economics_read_reuses_order_owner_scope() -> None:
    authorizer = PostgresResourceReadAuthorizer(
        lambda: MemoryUoW((order("operator-1"),), (economics(),))
    )

    authorizer.require_economics_read(
        entity_ref="order-1",
        actor_id="operator-1",
    )

    with pytest.raises(AuthorizationError, match="outside the actor resource scope"):
        authorizer.require_economics_read(
            entity_ref="order-1",
            actor_id="operator-2",
        )


def test_missing_owner_fails_closed() -> None:
    authorizer = PostgresResourceReadAuthorizer(
        lambda: MemoryUoW((order(""),), (economics(),))
    )

    with pytest.raises(AuthorizationError):
        authorizer.require_order_read(order_id="order-1", actor_id="operator-1")


def test_unknown_resource_does_not_fall_back_to_permission() -> None:
    authorizer = PostgresResourceReadAuthorizer(
        lambda: MemoryUoW((), ())
    )

    with pytest.raises(KeyError, match="unknown order"):
        authorizer.require_order_read(order_id="missing", actor_id="operator-1")

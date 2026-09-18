from decimal import Decimal

import pytest

from shema_platform.domain.economics import (
    EconomicEntry,
    EconomicKind,
    EconomicsService,
)
from shema_platform.domain.money import Money
from shema_platform.domain.order import Order, OrderLine, OrderStatus


def make_order() -> Order:
    return Order(
        order_id="order-1",
        identity_id="identity-1",
        source_action_id="action-1",
        lines=(
            OrderLine(
                "line-1",
                "Погрузка",
                Decimal("2"),
                Money(1500, "RUB"),
            ),
            OrderLine(
                "line-2",
                "Такелаж",
                Decimal("1"),
                Money(3000, "RUB"),
            ),
        ),
    )


def test_order_total_uses_decimal_money() -> None:
    assert make_order().total == Money(6000, "RUB")


def test_order_lifecycle_is_explicit() -> None:
    order = make_order()
    confirmed = order.confirm()
    running = confirmed.start()
    completed = running.complete()

    assert confirmed.status is OrderStatus.CONFIRMED
    assert running.status is OrderStatus.IN_PROGRESS
    assert completed.status is OrderStatus.COMPLETED


def test_invalid_order_transition_is_rejected() -> None:
    with pytest.raises(ValueError, match="only confirmed"):
        make_order().start()


def test_economics_summary_tracks_revenue_and_costs() -> None:
    entries = (
        EconomicEntry(
            "e1",
            "order-1",
            EconomicKind.REVENUE,
            Money(6000, "RUB"),
            "order:order-1",
            __import__("datetime").datetime.now(__import__("datetime").UTC),
        ),
        EconomicEntry(
            "e2",
            "order-1",
            EconomicKind.ORDER_COST,
            Money(2500, "RUB"),
            "cost:order-1",
            __import__("datetime").datetime.now(__import__("datetime").UTC),
        ),
    )

    summary = EconomicsService().summarize(entries)

    assert summary.revenue == Money(6000, "RUB")
    assert summary.costs == Money(2500, "RUB")
    assert summary.gross_margin == Money(3500, "RUB")


def test_economics_rejects_currency_mismatch() -> None:
    entry = EconomicEntry(
        "e1",
        "order-1",
        EconomicKind.REVENUE,
        Money(6000, "RUB"),
        "order:order-1",
        __import__("datetime").datetime.now(__import__("datetime").UTC),
    )

    with pytest.raises(ValueError, match="currency mismatch"):
        EconomicsService().summarize((entry,), currency="USD")

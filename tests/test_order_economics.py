from datetime import UTC, datetime
from decimal import Decimal

import pytest

from shema_platform.domain.economics import (
    EconomicEntry,
    EconomicKind,
    EconomicsService,
)
from shema_platform.domain.money import Money
from shema_platform.domain.order import Order, OrderLine, OrderStatus


def now() -> datetime:
    return datetime.now(UTC)


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


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (OrderStatus.DRAFT, OrderStatus.CANCELLED),
        (OrderStatus.CONFIRMED, OrderStatus.CANCELLED),
        (OrderStatus.IN_PROGRESS, OrderStatus.CANCELLED),
    ],
)
def test_order_can_be_cancelled_from_non_terminal_states(
    status: OrderStatus,
    expected: OrderStatus,
) -> None:
    order = make_order()
    if status is OrderStatus.CONFIRMED:
        order = order.confirm()
    elif status is OrderStatus.IN_PROGRESS:
        order = order.confirm().start()

    cancelled = order.cancel()

    assert cancelled.status is expected


def test_order_can_fail_only_while_in_progress() -> None:
    failed = make_order().confirm().start().fail()

    assert failed.status is OrderStatus.FAILED


@pytest.mark.parametrize(
    "status",
    [OrderStatus.COMPLETED, OrderStatus.CANCELLED, OrderStatus.FAILED],
)
def test_order_terminal_states_cannot_transition(status: OrderStatus) -> None:
    order = make_order()
    if status is OrderStatus.COMPLETED:
        order = order.confirm().start().complete()
    elif status is OrderStatus.CANCELLED:
        order = order.cancel()
    else:
        order = order.confirm().start().fail()

    with pytest.raises(ValueError):
        order.cancel()
    with pytest.raises(ValueError):
        order.fail()


def test_invalid_order_transition_is_rejected() -> None:
    with pytest.raises(ValueError, match="only confirmed"):
        make_order().start()

    with pytest.raises(ValueError, match="only in-progress"):
        make_order().fail()


def test_negative_unit_price_is_rejected() -> None:
    with pytest.raises(ValueError, match="unit price"):
        OrderLine("line-1", "Работа", Decimal("1"), Money(-1, "RUB"))


def test_money_float_conversion_is_deterministic() -> None:
    assert Money(0.1, "RUB") == Money("0.10", "RUB")


def test_economics_summary_tracks_revenue_and_costs() -> None:
    entries = (
        EconomicEntry(
            "e1",
            "order-1",
            EconomicKind.REVENUE,
            Money(6000, "RUB"),
            "order:order-1",
            now(),
        ),
        EconomicEntry(
            "e2",
            "order-1",
            EconomicKind.ORDER_COST,
            Money(2500, "RUB"),
            "cost:order-1",
            now(),
        ),
    )

    summary = EconomicsService().summarize(entries)

    assert summary.revenue == Money(6000, "RUB")
    assert summary.costs == Money(2500, "RUB")
    assert summary.gross_margin == Money(3500, "RUB")


def test_negative_revenue_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        EconomicEntry(
            "e1",
            "order-1",
            EconomicKind.REVENUE,
            Money(-1, "RUB"),
            "adjustment:bad",
            now(),
        )


def test_positive_adjustment_changes_revenue_lineage() -> None:
    entries = (
        EconomicEntry(
            "e1",
            "order-1",
            EconomicKind.REVENUE,
            Money(6000, "RUB"),
            "order:order-1",
            now(),
        ),
        EconomicEntry(
            "e2",
            "order-1",
            EconomicKind.ADJUSTMENT,
            Money(-500, "RUB"),
            "refund:order-1",
            now(),
        ),
    )

    summary = EconomicsService().summarize(entries)

    assert summary.revenue == Money(5500, "RUB")
    assert summary.gross_margin == Money(5500, "RUB")


def test_economics_rejects_currency_mismatch() -> None:
    entry = EconomicEntry(
        "e1",
        "order-1",
        EconomicKind.REVENUE,
        Money(6000, "RUB"),
        "order:order-1",
        now(),
    )

    with pytest.raises(ValueError, match="currency mismatch"):
        EconomicsService().summarize((entry,), currency="USD")

import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest

from shema_platform.domain.commercial_action import CommercialAction
from shema_platform.domain.economics import EconomicEntry, EconomicKind
from shema_platform.domain.money import Money
from shema_platform.domain.order import Order, OrderLine
from shema_platform.platform.postgres_repositories import (
    PostgresCommercialActionRepository,
    PostgresEconomicEntryRepository,
    PostgresOrderRepository,
)

pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("DATABASE_URL is not configured", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]


def apply_migrations(connection: psycopg.Connection) -> None:
    for name in (
        "0001_foundation.sql",
        "0002_discovery.sql",
        "0003_audit_context.sql",
        "0004_commercial_execution.sql",
    ):
        for statement in (ROOT / "db/migrations" / name).read_text().split(";"):
            statement = statement.strip()
            if statement:
                connection.execute(statement)


def ready_action() -> CommercialAction:
    return CommercialAction(
        action_id="action:integration",
        identity_id="identity:integration",
        contact_ref="chat:integration",
        channel="max",
        evidence_refs=("evidence:integration",),
    ).mark_ready()


def test_commercial_order_and_economics_round_trip() -> None:
    order = Order(
        order_id="order:integration",
        identity_id="identity:integration",
        source_action_id="action:integration",
        lines=(
            OrderLine(
                "line:integration",
                "Погрузка",
                Decimal("2"),
                Money("1500.00", "RUB"),
            ),
        ),
    )
    entry = EconomicEntry(
        "economic:integration",
        "order:integration",
        EconomicKind.REVENUE,
        Money("3000.00", "RUB"),
        "order:integration",
        datetime.now(UTC),
    )

    with psycopg.connect(DATABASE_URL) as connection:
        apply_migrations(connection)

        actions = PostgresCommercialActionRepository(connection)
        orders = PostgresOrderRepository(connection)
        economics = PostgresEconomicEntryRepository(connection)

        actions.add(ready_action())
        assert actions.get("action:integration") == ready_action()

        orders.add(order)
        assert orders.get("order:integration") == order

        economics.add(entry)
        assert economics.list_for_entity("order:integration") == (entry,)

        connection.commit()

        connection.execute(
            "delete from economic_entry where entry_id = %s",
            ("economic:integration",),
        )
        connection.execute(
            "delete from order_header where order_id = %s",
            ("order:integration",),
        )
        connection.execute(
            "delete from commercial_action where action_id = %s",
            ("action:integration",),
        )
        connection.commit()

import os
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from shema_platform.domain.money import Money
from shema_platform.domain.order import Order, OrderLine, OrderStatus
from shema_platform.platform.postgres_repositories import PostgresOrderRepository

pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("DATABASE_URL is not configured", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]


def apply_migration(connection: psycopg.Connection, path: Path) -> None:
    for statement in path.read_text().split(";"):
        statement = statement.strip()
        if statement:
            connection.execute(statement)


def prepare_database(connection: psycopg.Connection) -> None:
    for migration in (
        "0001_foundation.sql",
        "0002_discovery.sql",
        "0003_audit_context.sql",
        "0004_commercial_execution.sql",
        "0005_ai_run.sql",
        "0006_job_execution.sql",
        "0007_outbox_delivery_lease.sql",
        "0008_commercial_send_reservation.sql",
    ):
        apply_migration(connection, ROOT / "db/migrations" / migration)


def make_order() -> Order:
    return Order(
        order_id=f"order:{uuid4()}",
        identity_id=f"identity:{uuid4()}",
        source_action_id=f"action:{uuid4()}",
        lines=(
            OrderLine(
                line_id=f"line:{uuid4()}",
                description="Integration lifecycle test",
                quantity=Decimal("2"),
                unit_price=Money("1500.00", "RUB"),
            ),
        ),
    )


def test_postgres_order_repository_persists_full_lifecycle() -> None:
    order = make_order()

    with psycopg.connect(DATABASE_URL) as connection:
        prepare_database(connection)
        repository = PostgresOrderRepository(connection)

        repository.add(order)
        confirmed = order.confirm()
        repository.save(confirmed)
        in_progress = confirmed.start()
        repository.save(in_progress)
        failed = in_progress.fail()
        repository.save(failed)

        loaded = repository.get(order.order_id)
        assert loaded is not None
        assert loaded.status is OrderStatus.FAILED

        connection.rollback()


def test_postgres_order_repository_allows_cancellation_before_terminal_state() -> None:
    order = make_order()

    with psycopg.connect(DATABASE_URL) as connection:
        prepare_database(connection)
        repository = PostgresOrderRepository(connection)

        repository.add(order)
        repository.save(order.confirm().start().cancel())

        loaded = repository.get(order.order_id)
        assert loaded is not None
        assert loaded.status is OrderStatus.CANCELLED

        connection.rollback()

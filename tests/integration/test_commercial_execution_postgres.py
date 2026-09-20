import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

import psycopg
import pytest

from shema_platform.domain.commercial_action import CommercialAction
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.outbox import OutboxEvent
from shema_platform.domain.economics import EconomicEntry, EconomicKind
from shema_platform.domain.money import Money
from shema_platform.domain.order import Order, OrderLine, OrderStatus
from shema_platform.platform.postgres_repositories import (
    PostgresAuditRepository,
    PostgresCommercialActionRepository,
    PostgresEconomicEntryRepository,
    PostgresIdempotencyRepository,
    PostgresOrderRepository,
    PostgresOutboxRepository,
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
        "0008_commercial_send_reservation.sql",
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


def test_order_repository_rejects_invalid_persistence_transition() -> None:
    action = ready_action()
    order = Order(
        order_id="order:transition",
        identity_id=action.identity_id,
        source_action_id=action.action_id,
        lines=(
            OrderLine(
                "line:transition",
                "Погрузка",
                Decimal("1"),
                Money("1000.00", "RUB"),
            ),
        ),
    )

    with psycopg.connect(DATABASE_URL) as connection:
        apply_migrations(connection)
        orders = PostgresOrderRepository(connection)
        actions = PostgresCommercialActionRepository(connection)
        from shema_platform.foundation.errors import IntegrityViolation

        actions.add(action)
        orders.add(order)
        connection.commit()

        invalid = Order(
            order_id=order.order_id,
            identity_id=order.identity_id,
            source_action_id=order.source_action_id,
            lines=order.lines,
            status=OrderStatus.IN_PROGRESS,
        )
        with pytest.raises(IntegrityViolation, match="transition"):
            orders.save(invalid)
        connection.rollback()

        confirmed = order.confirm()
        orders.save(confirmed)
        connection.commit()
        assert orders.get(order.order_id) == confirmed

        connection.execute(
            "delete from order_header where order_id = %s",
            (order.order_id,),
        )
        connection.execute(
            "delete from commercial_action where action_id = %s",
            (action.action_id,),
        )
        connection.commit()


def test_commercial_completion_rolls_back_idempotency_business_outbox_and_audit() -> None:
    action = ready_action()
    action_id = action.action_id
    idempotency_key = "idempotency:atomic-completion"
    request_hash = "hash:atomic-completion"
    external_message_id = "max:atomic-completion"
    worker_id = "worker:atomic-completion"
    reservation_now = datetime.now(UTC)
    completion_now = reservation_now + timedelta(seconds=1)
    event_id = str(
        uuid5(
            NAMESPACE_URL,
            f"commercial-action.sent:{action_id}:{external_message_id}",
        )
    )
    audit_id = str(
        uuid5(
            NAMESPACE_URL,
            f"audit:commercial-action.sent:{action_id}:{external_message_id}",
        )
    )

    with psycopg.connect(DATABASE_URL) as connection:
        apply_migrations(connection)

        actions = PostgresCommercialActionRepository(connection)
        idempotency = PostgresIdempotencyRepository(connection)
        outbox = PostgresOutboxRepository(connection)
        audits = PostgresAuditRepository(connection)

        actions.add(action)
        connection.commit()

        idempotency.reserve(
            idempotency_key,
            request_hash,
            f"pending:{action_id}",
        )
        actions.claim_for_send(
            action_id,
            worker_id,
            lease_until=reservation_now + timedelta(minutes=5),
            now=reservation_now,
        )
        connection.commit()

        try:
            idempotency.complete(
                idempotency_key,
                request_hash,
                external_message_id,
            )
            sent = actions.complete_send(
                action_id,
                worker_id,
                now=completion_now,
            )
            event = OutboxEvent(
                event_id=event_id,
                event_type="commercial_action.sent",
                aggregate_type="commercial_action",
                aggregate_id=action_id,
                payload={
                    "action_id": action_id,
                    "identity_id": sent.identity_id,
                    "channel": sent.channel,
                    "external_message_id": external_message_id,
                },
                occurred_at=completion_now,
            )
            outbox.append(event)
            audits.append(
                AuditRecord(
                    audit_id=audit_id,
                    actor_id="operator:integration",
                    action="commercial_action.sent",
                    resource_type="commercial_action",
                    resource_id=action_id,
                    outcome="success",
                    occurred_at=completion_now,
                    metadata={"external_message_id": external_message_id},
                )
            )
            raise RuntimeError("simulated commit failure after all completion writes")
        except RuntimeError:
            connection.rollback()

        row = connection.execute(
            """
            select status, send_worker_id, send_lease_until
            from commercial_action
            where action_id = %s
            """,
            (action_id,),
        ).fetchone()
        assert row is not None
        assert row[0] == "sending"
        assert row[1] == worker_id
        assert row[2] is not None

        row = connection.execute(
            """
            select result_ref
            from idempotency_key
            where key = %s
            """,
            (idempotency_key,),
        ).fetchone()
        assert row == (f"pending:{action_id}",)

        assert (
            connection.execute(
                "select count(*) from outbox_event where event_id = %s",
                (event_id,),
            ).fetchone()
            == (0,)
        )
        assert (
            connection.execute(
                "select count(*) from audit_log where audit_id = %s",
                (audit_id,),
            ).fetchone()
            == (0,)
        )

        connection.execute(
            "delete from idempotency_key where key = %s",
            (idempotency_key,),
        )
        connection.execute(
            "delete from commercial_action where action_id = %s",
            (action_id,),
        )
        connection.commit()

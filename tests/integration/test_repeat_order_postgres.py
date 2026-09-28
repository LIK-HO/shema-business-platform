from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from shema_platform.application.commands import Actor
from shema_platform.application.repeat_order import (
    RepeatOrderService,
    RepeatOrderValidation,
)
from shema_platform.domain.identity import Identity, IdentityState
from shema_platform.domain.money import Money
from shema_platform.domain.order import Order, OrderLine, OrderStatus
from shema_platform.domain.repeat_order import (
    RepeatCadence,
    RepeatCadenceUnit,
    RepeatOrderContext,
)
from shema_platform.foundation.authorization import (
    AuthorizationSubject,
    Permission,
    RBACAuthorizer,
)
from shema_platform.foundation.errors import IntegrityViolation
from shema_platform.foundation.policy import PolicyEngine
from shema_platform.platform.migrations import MigrationPlan, MigrationRunner
from shema_platform.platform.postgres import PostgresUnitOfWork

pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("DATABASE_URL is not configured", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]


def make_schema() -> str:
    return "repeat_" + uuid4().hex


def connection(schema: str) -> psycopg.Connection:
    conn = psycopg.connect(DATABASE_URL)
    conn.execute('set search_path to "' + schema + '"')
    return conn


def migrate(schema: str) -> None:
    with psycopg.connect(DATABASE_URL) as bootstrap:
        bootstrap.execute('create schema "' + schema + '"')
        bootstrap.commit()
    plan = MigrationPlan.from_directory(ROOT / "db" / "migrations")
    MigrationRunner(lambda: connection(schema), plan).apply()


def factory(schema: str):
    return lambda: PostgresUnitOfWork(lambda: connection(schema))


def cleanup(schema: str) -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute('drop schema "' + schema + '" cascade')
        conn.commit()


def seed(schema: str, identity_id: str, source_order_id: str) -> None:
    with connection(schema) as conn:
        from shema_platform.platform.postgres_repositories import (
            PostgresIdentityRepository,
            PostgresOrderRepository,
        )

        PostgresIdentityRepository(conn).add(
            Identity(
                identity_id,
                "ООО Repeat Integration",
                IdentityState.VERIFIED,
                tax_id="7700000000",
            )
        )
        PostgresOrderRepository(conn).add(
            Order(
                source_order_id,
                identity_id,
                "action-repeat-source",
                (
                    OrderLine(
                        "source-line",
                        "Погрузка",
                        Decimal("2"),
                        Money(1500, "RUB"),
                    ),
                ),
                status=OrderStatus.COMPLETED,
            )
        )
        conn.commit()


class StaticRevalidator:
    def __init__(self, price: Decimal = Decimal("1500")) -> None:
        self.price = price

    def validate(self, *, identity, order, plan) -> RepeatOrderValidation:
        return RepeatOrderValidation(
            counterparty_ok=identity.state in {IdentityState.VERIFIED, IdentityState.ACTIVE},
            service_scope_ok=True,
            pricing_ok=True,
            date_capacity_ok=True,
            evidence_fresh_ok=True,
            resolved_lines=(
                OrderLine(
                    "repeat-line",
                    plan.context.service_scope,
                    plan.context.capacity_units,
                    Money(self.price, "RUB"),
                ),
            ),
        )


def service(schema: str, revalidator: StaticRevalidator | None = None):
    return RepeatOrderService(
        factory(schema),
        RBACAuthorizer(
            (
                AuthorizationSubject(
                    "operator-1",
                    frozenset({Permission.ORDER_CREATE}),
                ),
            )
        ),
        PolicyEngine(),
        revalidator or StaticRevalidator(),
        id_factory=lambda: str(uuid4()),
        clock=lambda: datetime(2026, 9, 28, 9, tzinfo=UTC),
    )


def actor() -> Actor:
    return Actor("operator-1", trust_level=2)


def context() -> RepeatOrderContext:
    return RepeatOrderContext(
        scheduled_for=datetime(2026, 10, 1, 9, tzinfo=UTC),
        service_scope="Погрузка",
        capacity_units=Decimal("2"),
    )


def test_postgres_repeat_order_lifecycle_is_atomic_and_durable() -> None:
    schema = make_schema()
    identity_id = str(uuid4())
    source_order_id = str(uuid4())
    try:
        migrate(schema)
        seed(schema, identity_id, source_order_id)
        workflow = service(schema)

        plan = workflow.create_plan(
            plan_id=str(uuid4()),
            source_order_id=source_order_id,
            actor=actor(),
            cadence=RepeatCadence(RepeatCadenceUnit.WEEK),
            context=context(),
            request_hash="plan-hash",
            idempotency_key="idem:repeat:plan",
            correlation_id="corr:repeat",
        )
        draft = workflow.create_next_repeat_order(
            actor=actor(),
            plan_id=plan.plan_id,
            request_hash="create-hash",
            idempotency_key="idem:repeat:create",
            correlation_id="corr:repeat",
        )
        confirmed = workflow.confirm_repeat_order(
            actor=actor(),
            plan_id=plan.plan_id,
            order_id=draft.order_id,
            request_hash="confirm-hash",
            idempotency_key="idem:repeat:confirm",
            correlation_id="corr:repeat",
        )

        with connection(schema) as conn:
            plan_row = conn.execute(
                """
                select status, pending_order_id, last_order_id, revision
                from repeat_order_plan
                where plan_id = %s
                """,
                (plan.plan_id,),
            ).fetchone()
            assert plan_row == ("active", None, confirmed.order_id, 3)

            assert conn.execute(
                "select status from order_header where order_id = %s",
                (confirmed.order_id,),
            ).fetchone() == ("confirmed",)

            assert conn.execute(
                """
                select amount from economic_entry
                where entity_ref = %s and kind = 'revenue'
                """,
                (confirmed.order_id,),
            ).fetchone() == (Decimal("3000.00"),)

            assert conn.execute(
                """
                select count(*)
                from audit_log
                where resource_type in ('repeat_order_plan', 'order')
                  and correlation_id = 'corr:repeat'
                """
            ).fetchone() == (3,)

            assert conn.execute(
                """
                select count(*)
                from outbox_event
                where aggregate_type in ('repeat_order_plan', 'order')
                """
            ).fetchone() == (3,)

            assert conn.execute(
                """
                select count(*) from idempotency_key
                where key in (
                    'idem:repeat:plan',
                    'idem:repeat:create',
                    'idem:repeat:confirm'
                )
                """
            ).fetchone() == (3,)
    finally:
        cleanup(schema)


def test_postgres_repeat_plan_revision_rejects_stale_operator_write() -> None:
    schema = make_schema()
    identity_id = str(uuid4())
    source_order_id = str(uuid4())
    try:
        migrate(schema)
        seed(schema, identity_id, source_order_id)
        workflow = service(schema)

        plan = workflow.create_plan(
            plan_id=str(uuid4()),
            source_order_id=source_order_id,
            actor=actor(),
            cadence=RepeatCadence(RepeatCadenceUnit.DAY),
            context=context(),
            request_hash="plan-hash",
            idempotency_key="idem:repeat:plan",
        )

        with factory(schema)() as first:
            first_plan = first.repeat_orders.get(plan.plan_id)
            assert first_plan is not None
            first.repeat_orders.save(
                first_plan.pause(),
                expected_revision=first_plan.revision,
            )

        with factory(schema)() as stale:
            stale_plan = stale.repeat_orders.get(plan.plan_id)
            assert stale_plan is not None
            with pytest.raises(IntegrityViolation, match="revision conflict"):
                stale.repeat_orders.save(
                    stale_plan.pause(),
                    expected_revision=plan.revision,
                )
    finally:
        cleanup(schema)


class FailingOutbox:
    def __init__(self, delegate) -> None:
        self._delegate = delegate

    def append(self, event):
        raise RuntimeError("simulated outbox failure")

    def __getattr__(self, name):
        return getattr(self._delegate, name)


class FailingOutboxUnitOfWork(PostgresUnitOfWork):
    def __enter__(self):
        super().__enter__()
        self.outbox = FailingOutbox(self.outbox)
        return self


def test_repeat_plan_rolls_back_when_audit_event_cannot_be_published() -> None:
    schema = make_schema()
    identity_id = str(uuid4())
    source_order_id = str(uuid4())
    plan_id = str(uuid4())
    try:
        migrate(schema)
        seed(schema, identity_id, source_order_id)

        workflow = RepeatOrderService(
            lambda: FailingOutboxUnitOfWork(lambda: connection(schema)),
            RBACAuthorizer(
                (
                    AuthorizationSubject(
                        "operator-1",
                        frozenset({Permission.ORDER_CREATE}),
                    ),
                )
            ),
            PolicyEngine(),
            StaticRevalidator(),
            clock=lambda: datetime(2026, 9, 28, 9, tzinfo=UTC),
        )

        with pytest.raises(RuntimeError, match="simulated outbox failure"):
            workflow.create_plan(
                plan_id=plan_id,
                source_order_id=source_order_id,
                actor=actor(),
                cadence=RepeatCadence(RepeatCadenceUnit.WEEK),
                context=context(),
                request_hash="plan-hash",
                idempotency_key="idem:repeat:rollback",
            )

        with connection(schema) as conn:
            assert conn.execute(
                "select count(*) from repeat_order_plan where plan_id = %s",
                (plan_id,),
            ).fetchone() == (0,)
            assert conn.execute(
                "select count(*) from idempotency_key where key = %s",
                ("idem:repeat:rollback",),
            ).fetchone() == (0,)
    finally:
        cleanup(schema)

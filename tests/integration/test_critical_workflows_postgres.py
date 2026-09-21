import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from shema_platform.application.commands import Actor
from shema_platform.application.critical_workflows import (
    CommercialActionCreateWorkflow,
    OrderCreateWorkflow,
)
from shema_platform.domain.commercial_action import CommercialActionStatus
from shema_platform.domain.identity import Identity, IdentityState
from shema_platform.domain.money import Money
from shema_platform.domain.order import OrderLine
from shema_platform.foundation.authorization import AuthorizationSubject, Permission, RBACAuthorizer
from shema_platform.foundation.errors import IdempotencyConflict
from shema_platform.foundation.policy import PolicyEngine
from shema_platform.platform.migrations import MigrationPlan, MigrationRunner
from shema_platform.platform.postgres import PostgresUnitOfWork

pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("DATABASE_URL is not configured", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]


def make_schema() -> str:
    return "workflow_" + uuid4().hex


def connection(schema: str) -> psycopg.Connection:
    conn = psycopg.connect(DATABASE_URL)
    conn.execute('set search_path to "' + schema + '"')
    return conn


def migrate(schema: str) -> None:
    plan = MigrationPlan.from_directory(ROOT / "db" / "migrations")
    MigrationRunner(lambda: connection(schema), plan).apply()


def factory(schema: str):
    return lambda: PostgresUnitOfWork(lambda: connection(schema))


def authorizer(permission: Permission) -> RBACAuthorizer:
    return RBACAuthorizer(
        (
            AuthorizationSubject(
                "operator-1",
                frozenset({permission}),
            ),
        )
    )


def cleanup(schema: str) -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute('drop schema "' + schema + '" cascade')
        conn.commit()


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


def seed_verified_identity(schema: str, identity_id: str) -> None:
    with connection(schema) as conn:
        from shema_platform.platform.postgres_repositories import PostgresIdentityRepository

        PostgresIdentityRepository(conn).add(
            Identity(
                identity_id,
                "ООО Integration",
                IdentityState.VERIFIED,
                tax_id="7700000000",
            )
        )
        conn.commit()


def test_critical_create_workflows_are_atomic_and_idempotent() -> None:
    schema = make_schema()
    try:
        migrate(schema)
        identity_id = str(uuid4())
        seed_verified_identity(schema, identity_id)

        action_workflow = CommercialActionCreateWorkflow(
            factory(schema),
            authorizer(Permission.COMMERCIAL_ACTION_CREATE),
            PolicyEngine(),
        )
        actor = Actor("operator-1", trust_level=2)

        action = action_workflow.execute(
            action_id="action-workflow-1",
            actor=actor,
            identity_id=identity_id,
            contact_ref="chat:integration",
            channel="max",
            evidence_refs=("evidence:integration",),
            request_hash="request:action:1",
            idempotency_key="idem:action:1",
            correlation_id="corr:workflow",
        )
        assert action.status is CommercialActionStatus.READY

        repeated = action_workflow.execute(
            action_id="action-workflow-1",
            actor=actor,
            identity_id=identity_id,
            contact_ref="chat:integration",
            channel="max",
            evidence_refs=("evidence:integration",),
            request_hash="request:action:1",
            idempotency_key="idem:action:1",
            correlation_id="corr:workflow",
        )
        assert repeated == action

        with psycopg.connect(DATABASE_URL) as conn:
            conn.execute('set search_path to "' + schema + '"')
            action_rows = conn.execute(
                "select count(*) from commercial_action where action_id = 'action-workflow-1'"
            ).fetchone()
            audit_rows = conn.execute(
                "select count(*) from audit_log where action = 'commercial_action.created'"
            ).fetchone()
            assert action_rows == (1,)
            assert audit_rows == (1,)
            idempotency_rows = conn.execute(
                "select count(*) from idempotency_key where key = 'idem:action:1'"
            ).fetchone()

            assert idempotency_rows == (1,)

            # Event id is UUIDv5; verify by querying aggregate/type instead of
            # duplicating UUID generation in the assertion.
            event_by_type = conn.execute(
                "select count(*) from outbox_event "
                "where event_type = 'commercial_action.created' "
                "and aggregate_id = 'action-workflow-1'"
            ).fetchone()
            assert event_by_type == (1,)

        with factory(schema)() as uow:
            sending = uow.commercial_actions.claim_for_send(
                "action-workflow-1",
                "integration-send",
                lease_until=datetime.now(UTC) + timedelta(minutes=1),
                now=datetime.now(UTC),
            )
            assert sending.status is CommercialActionStatus.SENDING
            uow.commercial_actions.complete_send(
                "action-workflow-1",
                "integration-send",
                now=datetime.now(UTC),
            )

        order_workflow = OrderCreateWorkflow(
            factory(schema),
            authorizer(Permission.ORDER_CREATE),
            PolicyEngine(),
        )
        order = order_workflow.execute(
            order_id="order-workflow-1",
            actor=actor,
            action_id="action-workflow-1",
            lines=(
                OrderLine(
                    "line-1",
                    "Погрузка",
                    Decimal("1"),
                    Money(1000, "RUB"),
                ),
            ),
            request_hash="request:order:1",
            idempotency_key="idem:order:1",
            correlation_id="corr:order",
        )
        assert order.order_id == "order-workflow-1"

        repeated_order = order_workflow.execute(
            order_id="order-workflow-1",
            actor=actor,
            action_id="action-workflow-1",
            lines=order.lines,
            request_hash="request:order:1",
            idempotency_key="idem:order:1",
            correlation_id="corr:order",
        )
        assert repeated_order == order

        with psycopg.connect(DATABASE_URL) as conn:
            conn.execute('set search_path to "' + schema + '"')
            assert conn.execute(
                "select count(*) from order_header where order_id = 'order-workflow-1'"
            ).fetchone() == (1,)
            assert conn.execute(
                "select count(*) from outbox_event "
                "where event_type = 'order.created' and aggregate_id = 'order-workflow-1'"
            ).fetchone() == (1,)
            assert conn.execute(
                "select count(*) from audit_log where action = 'order.created'"
            ).fetchone() == (1,)
            assert conn.execute(
                "select count(*) from idempotency_key where key = 'idem:order:1'"
            ).fetchone() == (1,)
    finally:
        cleanup(schema)


def test_critical_create_rolls_back_all_state_when_outbox_fails() -> None:
    schema = make_schema()
    try:
        migrate(schema)
        identity_id = str(uuid4())
        seed_verified_identity(schema, identity_id)

        workflow = CommercialActionCreateWorkflow(
            lambda: FailingOutboxUnitOfWork(lambda: connection(schema)),
            authorizer(Permission.COMMERCIAL_ACTION_CREATE),
            PolicyEngine(),
        )

        with pytest.raises(RuntimeError, match="simulated outbox failure"):
            workflow.execute(
                action_id="action-rollback-1",
                actor=Actor("operator-1", trust_level=2),
                identity_id=identity_id,
                contact_ref="chat:rollback",
                channel="max",
                evidence_refs=("evidence:rollback",),
                request_hash="request:rollback:1",
                idempotency_key="idem:rollback:1",
            )

        with psycopg.connect(DATABASE_URL) as conn:
            conn.execute('set search_path to "' + schema + '"')
            assert conn.execute(
                "select count(*) from commercial_action where action_id = 'action-rollback-1'"
            ).fetchone() == (0,)
            assert conn.execute(
                "select count(*) from idempotency_key where key = 'idem:rollback:1'"
            ).fetchone() == (0,)
            assert conn.execute(
                "select count(*) from audit_log where action = 'commercial_action.created'"
            ).fetchone() == (0,)
            assert conn.execute(
                "select count(*) from outbox_event where event_type = 'commercial_action.created'"
            ).fetchone() == (0,)
    finally:
        cleanup(schema)


def test_critical_create_rejects_changed_request_for_same_idempotency_key() -> None:
    schema = make_schema()
    try:
        migrate(schema)
        identity_id = str(uuid4())
        seed_verified_identity(schema, identity_id)

        workflow = CommercialActionCreateWorkflow(
            factory(schema),
            authorizer(Permission.COMMERCIAL_ACTION_CREATE),
            PolicyEngine(),
        )
        actor = Actor("operator-1", trust_level=2)
        workflow.execute(
            action_id="action-collision-1",
            actor=actor,
            identity_id=identity_id,
            contact_ref="chat:collision",
            channel="max",
            evidence_refs=("evidence:collision",),
            request_hash="request:collision:1",
            idempotency_key="idem:collision:1",
        )

        with pytest.raises(IdempotencyConflict):
            workflow.execute(
                action_id="action-collision-1",
                actor=actor,
                identity_id=identity_id,
                contact_ref="chat:changed",
                channel="max",
                evidence_refs=("evidence:collision",),
                request_hash="request:collision:2",
                idempotency_key="idem:collision:1",
            )
    finally:
        cleanup(schema)


def test_concurrent_action_create_with_same_idempotency_key_returns_one_result() -> None:
    schema = make_schema()
    try:
        migrate(schema)
        identity_id = str(uuid4())
        seed_verified_identity(schema, identity_id)

        barrier = Barrier(2)

        def execute_once():
            workflow = CommercialActionCreateWorkflow(
                factory(schema),
                authorizer(Permission.COMMERCIAL_ACTION_CREATE),
                PolicyEngine(),
            )
            barrier.wait(timeout=10)
            return workflow.execute(
                action_id="action-concurrent-1",
                actor=Actor("operator-1", trust_level=2),
                identity_id=identity_id,
                contact_ref="chat:concurrent",
                channel="max",
                evidence_refs=("evidence:concurrent",),
                request_hash="request:concurrent:1",
                idempotency_key="idem:concurrent:1",
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(execute_once),
                executor.submit(execute_once),
            ]
            results = [future.result(timeout=30) for future in futures]

        assert results[0] == results[1]

        with psycopg.connect(DATABASE_URL) as conn:
            conn.execute('set search_path to "' + schema + '"')
            assert conn.execute(
                "select count(*) from commercial_action "
                "where action_id = 'action-concurrent-1'"
            ).fetchone() == (1,)
            assert conn.execute(
                "select count(*) from idempotency_key "
                "where key = 'idem:concurrent:1'"
            ).fetchone() == (1,)
            assert conn.execute(
                "select count(*) from outbox_event "
                "where event_type = 'commercial_action.created' "
                "and aggregate_id = 'action-concurrent-1'"
            ).fetchone() == (1,)
            assert conn.execute(
                "select count(*) from audit_log "
                "where action = 'commercial_action.created' "
                "and resource_id = 'action-concurrent-1'"
            ).fetchone() == (1,)
    finally:
        cleanup(schema)

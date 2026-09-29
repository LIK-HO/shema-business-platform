from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from shema_platform.application.counterparty_check import (
    CounterpartyIdentifierType,
    CounterpartyObservation,
    SourceReliability,
)
from shema_platform.application.counterparty_monitoring import (
    ChangeSeverity,
    CounterpartyMonitoringService,
)
from shema_platform.foundation.authorization import Permission
from shema_platform.platform.migrations import MigrationPlan, MigrationRunner
from shema_platform.platform.postgres import PostgresUnitOfWork

pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("DATABASE_URL is not configured", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 9, 29, 13, tzinfo=UTC)
PERMISSIONS = frozenset(
    {
        Permission.COUNTERPARTY_MONITOR_MANAGE,
        Permission.COUNTERPARTY_FAVORITE_MANAGE,
    }
)


def make_schema() -> str:
    return "counterparty_monitor_" + uuid4().hex


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


def cleanup(schema: str) -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute('drop schema "' + schema + '" cascade')
        conn.commit()


def service(schema: str) -> CounterpartyMonitoringService:
    return CounterpartyMonitoringService(
        lambda: PostgresUnitOfWork(lambda: connection(schema))
    )


def observation(
    *,
    name='ООО "Пример"',
    status="ACTIVE",
    observed_at=NOW,
    expires_at=None,
) -> CounterpartyObservation:
    return CounterpartyObservation(
        identifier_type=CounterpartyIdentifierType.INN,
        identifier="7707083893",
        canonical_name=name,
        tax_id="7707083893",
        registration_id="1027700132195",
        legal_status=status,
        source_ref="https://pb.nalog.ru/",
        source_reliability=SourceReliability.AUTHORITATIVE,
        claim_confidence=1.0,
        observed_at=observed_at,
        expires_at=expires_at or observed_at + timedelta(days=1),
    )


def test_postgres_monitor_favorite_snapshot_and_change_are_durable() -> None:
    schema = make_schema()
    try:
        migrate(schema)
        workflow = service(schema)

        monitor = workflow.save_monitoring(
            identifier_type=CounterpartyIdentifierType.INN,
            identifier="7707083893",
            actor_id="operator-1",
            permissions=PERMISSIONS,
            idempotency_key="monitor-pg-1",
            correlation_id="corr-monitor-pg-1",
            now=NOW,
        )
        same_monitor = workflow.save_monitoring(
            identifier_type=CounterpartyIdentifierType.INN,
            identifier="7707083893",
            actor_id="operator-1",
            permissions=PERMISSIONS,
            idempotency_key="monitor-pg-2",
            correlation_id="corr-monitor-pg-2",
            now=NOW,
        )
        favorite = workflow.save_favorite(
            identifier_type=CounterpartyIdentifierType.INN,
            identifier="7707083893",
            actor_id="operator-1",
            permissions=PERMISSIONS,
            idempotency_key="favorite-pg-1",
            correlation_id="corr-favorite-pg",
            now=NOW,
        )

        assert same_monitor.monitor_id == monitor.monitor_id
        assert workflow.list_monitors("operator-1", PERMISSIONS) == (monitor,)
        assert workflow.list_favorites("operator-1", PERMISSIONS) == (favorite,)

        first = workflow.record_observation(
            monitor_id=monitor.monitor_id,
            actor_id="operator-1",
            permissions=PERMISSIONS,
            observation=observation(),
            correlation_id="corr-snapshot-1",
            now=NOW,
        )
        second = workflow.record_observation(
            monitor_id=monitor.monitor_id,
            actor_id="operator-1",
            permissions=PERMISSIONS,
            observation=observation(
                name='ООО "Новое"',
                observed_at=NOW + timedelta(days=1),
                expires_at=NOW + timedelta(days=2),
            ),
            correlation_id="corr-snapshot-2",
            now=NOW + timedelta(days=1),
        )

        assert first.snapshot_id != second.snapshot_id

        with connection(schema) as conn:
            assert conn.execute(
                "select count(*) from counterparty_monitor where actor_id = 'operator-1'"
            ).fetchone() == (1,)
            assert conn.execute(
                "select count(*) from counterparty_favorite where actor_id = 'operator-1'"
            ).fetchone() == (1,)
            assert conn.execute(
                "select count(*) from counterparty_snapshot where monitor_id = %s",
                (monitor.monitor_id,),
            ).fetchone() == (2,)
            change = conn.execute(
                """
                select severity, freshness, changed_parameters
                from counterparty_change_event
                where monitor_id = %s
                """,
                (monitor.monitor_id,),
            ).fetchone()
            assert change is not None
            assert change[0] == ChangeSeverity.ATTENTION.value
            assert change[1] == "FRESH"
            assert change[2]["canonical_name"]["before"] == 'ООО "Пример"'
            assert change[2]["canonical_name"]["after"] == 'ООО "Новое"'

            event = conn.execute(
                """
                select event_type, payload->>'severity'
                from outbox_event
                where aggregate_id = %s
                  and event_type = 'counterparty.change.detected'
                """,
                (monitor.monitor_id,),
            ).fetchone()
            assert event == ("counterparty.change.detected", "ATTENTION")

            audit_count = conn.execute(
                """
                select count(*)
                from audit_log
                where resource_type = 'counterparty_monitor'
                  and resource_id = %s
                """,
                (monitor.monitor_id,),
            ).fetchone()
            assert audit_count == (1,)
    finally:
        cleanup(schema)


def test_postgres_monitor_scope_rejects_cross_actor_snapshot_access() -> None:
    schema = make_schema()
    try:
        migrate(schema)
        workflow = service(schema)
        monitor = workflow.save_monitoring(
            identifier_type=CounterpartyIdentifierType.INN,
            identifier="7707083893",
            actor_id="operator-1",
            permissions=PERMISSIONS,
            idempotency_key="monitor-scope-1",
            correlation_id="corr-scope-1",
            now=NOW,
        )

        with pytest.raises(Exception, match="monitor is missing or outside actor scope"):
            workflow.record_observation(
                monitor_id=monitor.monitor_id,
                actor_id="operator-2",
                permissions=PERMISSIONS,
                observation=observation(),
                correlation_id="corr-scope-2",
                now=NOW,
            )
    finally:
        cleanup(schema)

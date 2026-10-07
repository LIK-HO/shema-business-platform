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
from shema_platform.application.counterparty_monitoring import CounterpartyMonitoringService
from shema_platform.application.counterparty_monitoring_worker import (
    BatchItemState,
    BatchStatus,
    CounterpartyMonitoringProviderError,
    CounterpartyMonitoringWorker,
)
from shema_platform.foundation.authorization import Permission
from shema_platform.foundation.errors import IntegrityViolation
from shema_platform.platform.migrations import MigrationPlan, MigrationRunner
from shema_platform.platform.postgres import PostgresUnitOfWork

pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("DATABASE_URL is not configured", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 9, 29, 15, tzinfo=UTC)
PERMISSIONS = frozenset({Permission.COUNTERPARTY_MONITOR_MANAGE})


class ScriptedProvider:
    def __init__(self, values):
        self.values = list(values)
        self.calls = 0

    def observe(self, monitor, *, now):
        value = self.values[min(self.calls, len(self.values) - 1)]
        self.calls += 1
        if isinstance(value, Exception):
            raise value
        return value


def connection(schema: str) -> psycopg.Connection:
    conn = psycopg.connect(DATABASE_URL)
    conn.execute('set search_path to "' + schema + '"')
    return conn


def make_schema() -> str:
    return "counterparty_monitor_worker_" + uuid4().hex


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


def factory(schema: str):
    return lambda: PostgresUnitOfWork(lambda: connection(schema))


def observation(observed_at: datetime = NOW) -> CounterpartyObservation:
    return CounterpartyObservation(
        identifier_type=CounterpartyIdentifierType.INN,
        identifier="7707083893",
        canonical_name='ООО "Пример"',
        tax_id="7707083893",
        registration_id="1027700132195",
        legal_status="ACTIVE",
        source_ref="https://pb.nalog.ru/",
        source_reliability=SourceReliability.AUTHORITATIVE,
        claim_confidence=1.0,
        observed_at=observed_at,
        expires_at=observed_at + timedelta(days=1),
    )


def test_postgres_checkpointed_monitoring_outage_recovery_and_duplicate_batch():
    schema = make_schema()
    try:
        migrate(schema)
        uow_factory = factory(schema)
        service = CounterpartyMonitoringService(uow_factory)
        monitor = service.save_monitoring(
            identifier_type=CounterpartyIdentifierType.INN,
            identifier="7707083893",
            actor_id="operator-1",
            permissions=PERMISSIONS,
            idempotency_key="worker-monitor-1",
            correlation_id="corr-worker-1",
            now=NOW,
        )

        provider = ScriptedProvider(
            [
                CounterpartyMonitoringProviderError(
                    "PROVIDER_UNAVAILABLE",
                    "registry unavailable",
                    retryable=True,
                ),
                observation(),
                observation(),
            ]
        )

        worker = CounterpartyMonitoringWorker(
            uow_factory,
            provider,
            worker_id="worker-1",
            permissions=PERMISSIONS,
            max_parallelism=2,
            lease_seconds=60,
            max_attempts=3,
            backoff_seconds=1,
            max_backoff_seconds=8,
            materialization_limit=100,
            clock=lambda: NOW,
        )

        first = worker.run_once(
            scheduled_at=NOW,
            batch_key="daily-2026-09-29",
        )
        assert first.batch_status is BatchStatus.RUNNING
        assert first.retryable == 1

        with connection(schema) as conn:
            assert conn.execute(
                "select count(*) from counterparty_snapshot where monitor_id = %s",
                (monitor.monitor_id,),
            ).fetchone() == (0,)
            item = conn.execute(
                """
                select state, last_error_code
                from counterparty_monitoring_batch_item
                where batch_id = %s and monitor_id = %s
                """,
                (first.batch_id, monitor.monitor_id),
            ).fetchone()
            assert item == (BatchItemState.RETRYABLE.value, "PROVIDER_UNAVAILABLE")

            with connection(schema) as conn:
                raw_claim = conn.execute(
                    "select state, attempt "
                    "from counterparty_monitoring_batch_item "
                    "where batch_id = %s and monitor_id = %s "
                    "and available_at <= %s "
                    "and (state in ('pending', 'retryable') "
                    "or (state = 'running' and lease_until < %s)) "
                    "for update skip locked limit 1",
                    (
                        first.batch_id,
                        monitor.monitor_id,
                        NOW + timedelta(seconds=2),
                        NOW + timedelta(seconds=2),
                    ),
                ).fetchone()
                print("RAW SKIP LOCKED AFTER COMMIT", raw_claim)

            with connection(schema) as conn:
                conn.execute(
                    "select batch_id "
                    "from counterparty_monitoring_batch "
                    "where batch_id = %s for update",
                    (first.batch_id,),
                )
                parent_locked_claim = conn.execute(
                    "select state, attempt "
                    "from counterparty_monitoring_batch_item "
                    "where batch_id = %s and monitor_id = %s "
                    "and available_at <= %s "
                    "and (state in ('pending', 'retryable') "
                    "or (state = 'running' and lease_until < %s)) "
                    "for update skip locked limit 1",
                    (
                        first.batch_id,
                        monitor.monitor_id,
                        NOW + timedelta(seconds=2),
                        NOW + timedelta(seconds=2),
                    ),
                ).fetchone()
                print("RAW AFTER PARENT LOCK", parent_locked_claim)

            with connection(schema) as conn:
                conn.execute(
                    "insert into counterparty_monitoring_batch "
                    "(batch_id, batch_key, scheduled_at, status, next_cursor, collection_complete, created_at, completed_at) "
                    "values (%s, %s, %s, 'collecting', null, false, %s, null) "
                    "on conflict (batch_key) do nothing",
                    (
                        first.batch_id,
                        "daily-2026-09-29",
                        NOW + timedelta(seconds=2),
                        NOW + timedelta(seconds=2),
                    ),
                )
                conn.execute(
                    "select batch_id, collection_complete "
                    "from counterparty_monitoring_batch where batch_key = %s",
                    ("daily-2026-09-29",),
                ).fetchone()
                seq_after_conflict_insert = conn.execute(
                    "select state, attempt "
                    "from counterparty_monitoring_batch_item "
                    "where batch_id = %s and monitor_id = %s "
                    "and available_at <= %s "
                    "and (state in ('pending', 'retryable') "
                    "or (state = 'running' and lease_until < %s)) "
                    "for update skip locked limit 1",
                    (
                        first.batch_id,
                        monitor.monitor_id,
                        NOW + timedelta(seconds=2),
                        NOW + timedelta(seconds=2),
                    ),
                ).fetchone()
                print("RAW AFTER CONFLICT INSERT", seq_after_conflict_insert)

        recovery = CounterpartyMonitoringWorker(
            uow_factory,
            provider,
            worker_id="worker-2",
            permissions=PERMISSIONS,
            max_parallelism=1,
            lease_seconds=60,
            max_attempts=3,
            backoff_seconds=1,
            max_backoff_seconds=8,
            materialization_limit=100,
            clock=lambda: NOW + timedelta(seconds=2),
        )
        second = recovery.run_once(
            scheduled_at=NOW + timedelta(seconds=2),
            batch_key="daily-2026-09-29",
        )
        assert second.batch_status is BatchStatus.COMPLETED
        assert second.completed == 1

        with connection(schema) as conn:
            assert conn.execute(
                "select count(*) from counterparty_snapshot where monitor_id = %s",
                (monitor.monitor_id,),
            ).fetchone() == (1,)
            assert conn.execute(
                "select count(*) from counterparty_change_event where monitor_id = %s",
                (monitor.monitor_id,),
            ).fetchone() == (0,)
            assert conn.execute(
                "select last_error_code from counterparty_monitor where monitor_id = %s",
                (monitor.monitor_id,),
            ).fetchone() == (None,)

        duplicate = recovery.run_once(
            scheduled_at=NOW + timedelta(seconds=2),
            batch_key="daily-2026-09-29",
        )
        assert duplicate.claimed == 0
        assert provider.calls == 2

        with connection(schema) as conn:
            conn.execute(
                """
                update counterparty_monitoring_batch_item
                set state = 'running',
                    lease_worker_id = 'dead-worker',
                    lease_until = %s
                where batch_id = %s and monitor_id = %s
                """,
                (
                    NOW - timedelta(seconds=1),
                    second.batch_id,
                    monitor.monitor_id,
                ),
            )
            conn.commit()

        replay = CounterpartyMonitoringWorker(
            uow_factory,
            provider,
            worker_id="recovery-worker",
            permissions=PERMISSIONS,
            max_parallelism=1,
            lease_seconds=60,
            max_attempts=3,
            backoff_seconds=1,
            max_backoff_seconds=8,
            materialization_limit=100,
            clock=lambda: NOW,
        )
        replay_result = replay.run_once(
            scheduled_at=NOW,
            batch_key="daily-2026-09-29",
        )
        assert replay_result.completed == 1
        assert replay_result.batch_status is BatchStatus.COMPLETED

        with connection(schema) as conn:
            assert conn.execute(
                "select count(*) from counterparty_snapshot where monitor_id = %s",
                (monitor.monitor_id,),
            ).fetchone() == (1,)
    finally:
        cleanup(schema)

def test_postgres_stale_worker_cannot_complete_reclaimed_batch_item():
    schema = make_schema()
    try:
        migrate(schema)
        uow_factory = factory(schema)
        service = CounterpartyMonitoringService(uow_factory)
        monitor = service.save_monitoring(
            identifier_type=CounterpartyIdentifierType.INN,
            identifier="7707083893",
            actor_id="operator-1",
            permissions=PERMISSIONS,
            idempotency_key="worker-race-monitor",
            correlation_id="corr-worker-race",
            now=NOW,
        )
        with uow_factory() as uow:
            batch = uow.counterparty_monitoring_batches.start_or_resume_daily_batch(
                batch_key="daily-race",
                scheduled_at=NOW,
            )
            batch = uow.counterparty_monitoring_batches.materialize_due_items(
                batch.batch_id,
                scheduled_at=NOW,
                limit=10,
            )
            first_claim = uow.counterparty_monitoring_batches.claim_items(
                batch.batch_id,
                "worker-a",
                lease_seconds=1,
                now=NOW,
                limit=1,
            )
            assert first_claim[0].monitor_id == monitor.monitor_id

        with uow_factory() as uow:
            second_claim = uow.counterparty_monitoring_batches.claim_items(
                batch.batch_id,
                "worker-b",
                lease_seconds=60,
                now=NOW + timedelta(seconds=2),
                limit=1,
            )
            assert second_claim[0].monitor_id == monitor.monitor_id

        with pytest.raises(IntegrityViolation, match="stale or unauthorized"):
            with uow_factory() as uow:
                uow.counterparty_monitoring_batches.complete_item(
                    batch.batch_id,
                    monitor.monitor_id,
                    "worker-a",
                    now=NOW + timedelta(seconds=2),
                )
    finally:
        cleanup(schema)


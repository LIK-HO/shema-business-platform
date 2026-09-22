import os
import pathlib
import uuid

import psycopg
import pytest

from shema_platform.platform.migrations import (
    Migration,
    MigrationIntegrityError,
    MigrationPlan,
    MigrationRunner,
)

pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("DATABASE_URL is not configured", allow_module_level=True)

ROOT = pathlib.Path(__file__).resolve().parents[2]


def make_schema() -> str:
    return "migration_" + uuid.uuid4().hex


def connect(schema: str) -> psycopg.Connection:
    connection = psycopg.connect(DATABASE_URL)
    connection.execute("SET search_path TO \"" + schema + "\"")
    connection.commit()
    return connection


def test_migration_runner_is_idempotent_and_checksummed() -> None:
    schema = make_schema()
    with psycopg.connect(DATABASE_URL) as bootstrap:
        bootstrap.execute("create schema \"" + schema + "\"")
        bootstrap.commit()

    try:
        plan = MigrationPlan.from_directory(ROOT / "db" / "migrations")
        runner = MigrationRunner(lambda: connect(schema), plan)

        first = runner.apply()
        assert first.applied == tuple(range(1, len(plan.migrations) + 1))
        assert first.current_version == len(plan.migrations)

        second = runner.apply()
        assert second.applied == ()
        assert second.current_version == len(plan.migrations)

        with connect(schema) as check:
            row = check.execute("select count(*) from schema_migration").fetchone()
            assert row == (len(plan.migrations),)
    finally:
        with psycopg.connect(DATABASE_URL) as cleanup:
            cleanup.execute("drop schema \"" + schema + "\" cascade")
            cleanup.commit()


def test_migration_runner_rejects_historical_checksum_drift() -> None:
    schema = make_schema()
    with psycopg.connect(DATABASE_URL) as bootstrap:
        bootstrap.execute("create schema \"" + schema + "\"")
        bootstrap.commit()

    try:
        plan = MigrationPlan.from_directory(ROOT / "db" / "migrations")
        MigrationRunner(lambda: connect(schema), plan).apply()

        drifted = []
        for migration in plan.migrations:
            if migration.version == 1:
                drifted.append(
                    Migration(
                        migration.version,
                        migration.name,
                        migration.sql + "\n-- drift",
                    )
                )
            else:
                drifted.append(migration)

        with pytest.raises(MigrationIntegrityError, match="differs from approved checksum"):
            MigrationRunner(lambda: connect(schema), MigrationPlan(tuple(drifted))).apply()
    finally:
        with psycopg.connect(DATABASE_URL) as cleanup:
            cleanup.execute("drop schema \"" + schema + "\" cascade")
            cleanup.commit()

def test_state_ownership_constraints_reject_impossible_lease_shapes() -> None:
    schema = make_schema()
    with psycopg.connect(DATABASE_URL) as bootstrap:
        bootstrap.execute("create schema \"" + schema + "\"")
        bootstrap.commit()

    try:
        plan = MigrationPlan.from_directory(ROOT / "db" / "migrations")
        MigrationRunner(lambda: connect(schema), plan).apply()

        with connect(schema) as connection:
            with pytest.raises(psycopg.errors.CheckViolation):
                connection.execute(
                    """
                    insert into job_execution (
                        job_id, job_type, state, idempotency_key,
                        payload, available_at, worker_id
                    )
                    values ('invalid-job', 'test', 'queued', 'invalid-job',
                            '{}'::jsonb, now(), 'worker-1')
                    """
                )
            connection.rollback()

            with pytest.raises(psycopg.errors.CheckViolation):
                connection.execute(
                    """
                    insert into outbox_event (
                        event_id, event_type, aggregate_type, aggregate_id, payload,
                        delivery_worker_id
                    )
                    values (
                        '00000000-0000-0000-0000-000000000001',
                        'test', 'test', '1', '{}'::jsonb, 'worker-1'
                    )
                    """
                )
            connection.rollback()
    finally:
        with psycopg.connect(DATABASE_URL) as cleanup:
            cleanup.execute("drop schema \"" + schema + "\" cascade")
            cleanup.commit()

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

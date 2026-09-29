from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from shema_platform.application.public_intake import (
    PublicIntakePayload,
    PublicIntakeService,
)
from shema_platform.platform.migrations import MigrationPlan, MigrationRunner
from shema_platform.platform.public_intake_postgres import (
    PostgresPublicIntakeRepository,
)

pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("DATABASE_URL is not configured", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]


def admin_dsn(database: str) -> str:
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    values = conninfo_to_dict(DATABASE_URL)
    values["dbname"] = database
    return make_conninfo(**values)


def create_database(database: str) -> None:
    with psycopg.connect(admin_dsn("postgres"), autocommit=True) as conn:
        conn.execute(
            "select pg_terminate_backend(pid) from pg_stat_activity "
            "where datname = %s and pid <> pg_backend_pid()",
            (database,),
        )
        conn.execute(f'create database "{database}"')


def drop_database(database: str) -> None:
    with psycopg.connect(admin_dsn("postgres"), autocommit=True) as conn:
        conn.execute(
            "select pg_terminate_backend(pid) from pg_stat_activity "
            "where datname = %s and pid <> pg_backend_pid()",
            (database,),
        )
        conn.execute(f'drop database if exists "{database}"')


def intake_factory(database: str):
    def connect():
        return psycopg.connect(admin_dsn(database))

    return connect


class NeverCalledPreflight:
    def run(self, *, payload, request_id, correlation_id, public_client_key, now):
        from shema_platform.application.public_intake import (
            CounterpartyPreflightSnapshot,
            IdentityMatch,
            PreflightDecision,
        )

        return CounterpartyPreflightSnapshot(
            snapshot_id=f"preflight:{request_id}",
            identifier_type=None,
            normalized_identifier=None,
            decision=PreflightDecision.UNKNOWN,
            identity_match=IdentityMatch.NOT_CHECKED,
            canonical_name=None,
            legal_status=None,
            source_ref=None,
            provider_id=None,
            observed_at=now,
            expires_at=now,
            flags=("IDENTIFIER_NOT_PROVIDED",),
        )


class Projector:
    def __init__(self):
        self.calls = []

    def project(self, record):
        self.calls.append(record.request_id)


def payload() -> PublicIntakePayload:
    return PublicIntakePayload(
        service_type="Погрузка",
        location="Москва",
        preferred_date_or_period="2026-10-05",
        work_or_cargo_description="Погрузить оборудование",
        contact_name="Иван Петров",
        contact_channel="+79990000000",
        entry_surface="public_web",
    )


def migrate(database: str) -> None:
    MigrationRunner(
        intake_factory(database),
        MigrationPlan.from_directory(
            ROOT / "db" / "public_intake_migrations"
        ),
    ).apply()


def test_public_intake_database_is_isolated_durable_and_idempotent() -> None:
    database = f"shema_intake_{uuid4().hex[:12]}"
    try:
        create_database(database)
        migrate(database)
        def repository_factory():
            return PostgresPublicIntakeRepository(intake_factory(database))
        projector = Projector()
        service = PublicIntakeService(
            repository_factory,
            preflight=NeverCalledPreflight(),
            projector=projector,
            clock=lambda: datetime(2026, 9, 28, 12, tzinfo=UTC),
            enforce_edge_proof=False,
        )

        first = service.submit(
            payload=payload(),
            idempotency_key="integration-intake-1",
            public_client_key="integration-client-1",
            origin=None,
            bot_challenge_passed=False,
            correlation_id="corr-intake-1",
        )
        replay = service.submit(
            payload=payload(),
            idempotency_key="integration-intake-1",
            public_client_key="integration-client-1",
            origin=None,
            bot_challenge_passed=False,
            correlation_id="corr-intake-2",
        )

        assert replay.deduplicated is True
        assert replay.record.request_id == first.record.request_id
        assert projector.calls == [first.record.request_id]

        with psycopg.connect(admin_dsn(database)) as conn:
            assert conn.execute(
                "select count(*) from intake_request"
            ).fetchone() == (1,)
            assert conn.execute(
                "select count(*) from intake_outbox_event where published_at is null"
            ).fetchone() == (1,)
            assert conn.execute(
                "select count(*) from intake_preflight_snapshot"
            ).fetchone() == (1,)
            assert conn.execute(
                "select count(*) from intake_rate_limit"
            ).fetchone() == (1,)
            assert conn.execute(
                "select count(*) from intake_idempotency_reservation"
            ).fetchone() == (1,)

    finally:
        drop_database(database)


def test_public_intake_stale_outbox_worker_cannot_mark_reclaimed_event_published() -> None:
    with psycopg.connect(DATABASE_URL) as first, psycopg.connect(DATABASE_URL) as second:
        apply_migrations(first)
        from shema_platform.foundation.errors import IntegrityViolation

        event_id = f"stale-outbox:{uuid4()}"
        occurred_at = datetime.now(UTC)
        from shema_platform.platform.public_intake_postgres import (
            PostgresPublicIntakeRepository,
        )

        repository = PostgresPublicIntakeRepository(lambda: first)
        repository._connection = first
        repository.append_outbox(
            event_id=event_id,
            request_id=f"request:{uuid4()}",
            event_type="new_client_request",
            payload={"test": True},
            occurred_at=occurred_at,
            notify_operator=True,
        )
        first.commit()
        repository._connection = None

        old = PostgresPublicIntakeRepository(lambda: first)
        old._connection = first
        old_claim = old.claim_pending(
            "worker-old",
            lease_seconds=1,
            now=occurred_at,
            limit=1,
        )
        assert len(old_claim) == 1
        first.commit()
        old._connection = None

        new = PostgresPublicIntakeRepository(lambda: second)
        new._connection = second
        new_claim = new.claim_pending(
            "worker-new",
            lease_seconds=60,
            now=occurred_at + timedelta(seconds=2),
            limit=1,
        )
        assert len(new_claim) == 1
        second.commit()

        stale = PostgresPublicIntakeRepository(lambda: first)
        stale._connection = first
        with pytest.raises(IntegrityViolation, match="publication rejected"):
            stale.mark_outbox_published(
                event_id,
                worker_id="worker-old",
                now=occurred_at + timedelta(seconds=2),
            )
        first.rollback()
        stale._connection = None

        current = new
        row = second.execute(
            """
            select published_at, delivery_worker_id
            from intake_outbox_event
            where event_id = %s
            """,
            (event_id,),
        ).fetchone()
        assert row is not None
        assert row[0] is None
        assert row[1] == "worker-new"
        second.execute(
            "delete from intake_outbox_event where event_id = %s",
            (event_id,),
        )
        second.commit()


def test_public_intake_migration_can_be_adopted_by_a_fresh_database() -> None:
    database = f"shema_intake_{uuid4().hex[:12]}"
    try:
        create_database(database)
        report = MigrationRunner(
            intake_factory(database),
            MigrationPlan.from_directory(
                ROOT / "db" / "public_intake_migrations"
            ),
        ).apply()
        assert report.current_version == 3
        assert report.applied == (1, 2, 3)

        with psycopg.connect(admin_dsn(database)) as conn:
            assert conn.execute(
                "select count(*) from schema_migration where version = 3"
            ).fetchone() == (1,)
    finally:
        drop_database(database)

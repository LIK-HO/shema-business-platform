from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from shema_platform.application.public_intake import (
    CounterpartyPreflightSnapshot,
    IdentityMatch,
    IntakeStatus,
    PreflightDecision,
    PublicIntakePayload,
    PublicIntakeService,
)
from shema_platform.platform.migrations import MigrationPlan, MigrationRunner
from shema_platform.platform.postgres import PostgresUnitOfWork
from shema_platform.platform.public_intake_postgres import (
    PostgresOperatorNotificationReader,
    PostgresPublicIntakeRepository,
    PostgresPublicRequestProjection,
    PublicIntakeOutboxDispatcher,
)

pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("DATABASE_URL is not configured", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 9, 29, 12, tzinfo=UTC)


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


def connection(database: str) -> psycopg.Connection:
    return psycopg.connect(admin_dsn(database))


def migrate(database: str, directory: Path) -> None:
    plan = MigrationPlan.from_directory(directory)
    MigrationRunner(lambda: connection(database), plan).apply()


class StaticPreflight:
    def run(
        self,
        *,
        payload: PublicIntakePayload,
        request_id: str,
        correlation_id: str,
        public_client_key: str,
        now: datetime,
    ) -> CounterpartyPreflightSnapshot:
        return CounterpartyPreflightSnapshot(
            snapshot_id=f"preflight:{request_id}",
            identifier_type="INN" if payload.inn else None,
            normalized_identifier=payload.inn,
            decision=PreflightDecision.NORMAL,
            identity_match=IdentityMatch.MATCH,
            canonical_name=payload.company_name,
            legal_status="ACTIVE",
            source_ref="registry:test",
            provider_id="registry:test",
            observed_at=now,
            expires_at=now.replace(day=30),
        )


class FailingProjector:
    def project(self, record) -> None:
        raise RuntimeError("simulated canonical Shema outage")


def payload() -> PublicIntakePayload:
    return PublicIntakePayload(
        service_type="Погрузка",
        location="Москва",
        preferred_date_or_period="2026-10-05",
        work_or_cargo_description="Погрузить оборудование в офисе",
        contact_name="Иван Петров",
        contact_channel="+79990000000",
        company_name="ООО E2E",
        inn="7707083893",
        entry_surface="public_web",
    )


def test_public_intake_survives_shema_outage_and_replays_exactly_once() -> None:
    intake_database = f"shema_intake_e2e_{uuid4().hex[:12]}"
    canonical_database = f"shema_canonical_e2e_{uuid4().hex[:12]}"

    try:
        create_database(intake_database)
        create_database(canonical_database)
        migrate(intake_database, ROOT / "db" / "public_intake_migrations")
        migrate(canonical_database, ROOT / "db" / "migrations")

        def intake_connection() -> psycopg.Connection:
            return connection(intake_database)

        def intake_factory() -> PostgresPublicIntakeRepository:
            return PostgresPublicIntakeRepository(intake_connection)


        service = PublicIntakeService(
            intake_factory,
            preflight=StaticPreflight(),
            projector=FailingProjector(),
            enforce_edge_proof=False,
            allowed_origins=frozenset({"https://example.test"}),
            clock=lambda: NOW,
        )

        accepted = service.submit(
            payload=payload(),
            idempotency_key="e2e-public-intake-1",
            public_client_key="e2e-public-client",
            origin="https://example.test",
            bot_challenge_passed=True,
            correlation_id="corr:e2e-public-intake",
        )

        assert accepted.record.status is IntakeStatus.ACCEPTED
        assert accepted.projection_status == "PENDING_PROJECTION"

        with connection(intake_database) as intake:
            pending = intake.execute(
                """
                select request_id, projected_at
                from intake_request
                where request_id = %s
                """,
                (accepted.record.request_id,),
            ).fetchone()
            assert pending == (accepted.record.request_id, None)

            outbox = intake.execute(
                """
                select published_at
                from intake_outbox_event
                where request_id = %s
                  and event_type = 'new_client_request'
                """,
                (accepted.record.request_id,),
            ).fetchone()
            assert outbox == (None,)

        projection = PostgresPublicRequestProjection(
            lambda: PostgresUnitOfWork(lambda: connection(canonical_database)),
            clock=lambda: NOW,
        )
        dispatcher = PublicIntakeOutboxDispatcher(
            intake_factory,
            projection,
            worker_id="e2e-replay-worker",
            lease_seconds=60,
            clock=lambda: NOW,
        )

        replayed = dispatcher.dispatch_pending(limit=10)
        assert replayed == 1

        with connection(intake_database) as intake:
            projected = intake.execute(
                """
                select projected_at
                from intake_request
                where request_id = %s
                """,
                (accepted.record.request_id,),
            ).fetchone()
            assert projected is not None
            assert projected[0] is not None

            published = intake.execute(
                """
                select published_at, delivery_worker_id, delivery_lease_until
                from intake_outbox_event
                where request_id = %s
                  and event_type = 'new_client_request'
                """,
                (accepted.record.request_id,),
            ).fetchone()
            assert published is not None
            assert published[0] is not None
            assert published[1] is None
            assert published[2] is None

        with connection(canonical_database) as canonical:
            context = canonical.execute(
                """
                select request_id, correlation_id, status, preflight_decision,
                       preflight_identity_match, source_attribution
                from public_request_context
                where request_id = %s
                """,
                (accepted.record.request_id,),
            ).fetchone()
            assert context is not None
            assert context[0] == accepted.record.request_id
            assert context[1] == "corr:e2e-public-intake"
            assert context[2] == "ACCEPTED"
            assert context[3] == "NORMAL"
            assert context[4] == "MATCH"
            assert context[5]["entry_surface"] == "public_web"

            notification_count = canonical.execute(
                """
                select count(*)
                from operator_notification
                where request_id = %s
                  and event_type = 'new_client_request'
                """,
                (accepted.record.request_id,),
            ).fetchone()
            assert notification_count == (1,)

        notification_reader = PostgresOperatorNotificationReader(
            lambda: connection(canonical_database)
        )
        notifications = notification_reader.list_unread(limit=50)
        assert len(notifications) == 1
        assert notifications[0]["requestId"] == accepted.record.request_id

        second_replay = dispatcher.dispatch_pending(limit=10)
        assert second_replay == 0

        with connection(canonical_database) as canonical:
            assert canonical.execute(
                """
                select count(*)
                from operator_notification
                where request_id = %s
                  and event_type = 'new_client_request'
                """,
                (accepted.record.request_id,),
            ).fetchone() == (1,)

    finally:
        drop_database(intake_database)
        drop_database(canonical_database)

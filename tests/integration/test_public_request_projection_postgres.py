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
    PublicIntakeRecord,
)
from shema_platform.platform.migrations import MigrationPlan, MigrationRunner
from shema_platform.platform.postgres import PostgresUnitOfWork
from shema_platform.platform.public_intake_postgres import (
    PostgresOperatorNotificationReader,
    PostgresPublicRequestProjection,
)

pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("DATABASE_URL is not configured", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]


def make_schema() -> str:
    return "public_projection_" + uuid4().hex


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


def record() -> PublicIntakeRecord:
    now = datetime(2026, 9, 29, 11, tzinfo=UTC)
    return PublicIntakeRecord(
        request_id="public-request:" + uuid4().hex,
        correlation_id="corr:public-projection",
        idempotency_key="idem:public-projection",
        request_hash="request-hash",
        status=IntakeStatus.ACCEPTED,
        payload=PublicIntakePayload(
            service_type="Погрузка",
            location="Москва",
            preferred_date_or_period="2026-10-05",
            work_or_cargo_description="Погрузить оборудование",
            contact_name="Иван Петров",
            contact_channel="+79990000000",
            company_name="ООО Проекция",
            inn="7707083893",
            entry_surface="public_web",
        ),
        preflight=CounterpartyPreflightSnapshot(
            snapshot_id="preflight:public-projection",
            identifier_type="INN",
            normalized_identifier="7707083893",
            decision=PreflightDecision.NORMAL,
            identity_match=IdentityMatch.MATCH,
            canonical_name="ООО Проекция",
            legal_status="ACTIVE",
            source_ref="registry:test",
            provider_id="registry:test",
            observed_at=now,
            expires_at=datetime(2026, 10, 1, tzinfo=UTC),
        ),
        created_at=now,
    )


def test_public_intake_projection_schema_is_durable_and_replay_safe() -> None:
    schema = make_schema()
    try:
        migrate(schema)
        projection = PostgresPublicRequestProjection(
            lambda: PostgresUnitOfWork(lambda: connection(schema)),
            clock=lambda: datetime(2026, 9, 29, 11, 1, tzinfo=UTC),
        )
        notification_reader = PostgresOperatorNotificationReader(
            lambda: connection(schema)
        )
        accepted = record()

        projection.project(accepted)
        projection.project(accepted)

        with connection(schema) as conn:
            context = conn.execute(
                """
                select request_id, correlation_id, status, preflight_decision,
                       preflight_identity_match, source_attribution
                from public_request_context
                where request_id = %s
                """,
                (accepted.request_id,),
            ).fetchone()
            assert context is not None
            assert context[0] == accepted.request_id
            assert context[1] == accepted.correlation_id
            assert context[2] == "ACCEPTED"
            assert context[3] == "NORMAL"
            assert context[4] == "MATCH"
            assert context[5]["entry_surface"] == "public_web"

            notification_count = conn.execute(
                """
                select count(*)
                from operator_notification
                where request_id = %s
                """,
                (accepted.request_id,),
            ).fetchone()
            assert notification_count == (1,)

        notifications = notification_reader.list_unread(limit=50)
        assert len(notifications) == 1
        assert notifications[0]["requestId"] == accepted.request_id
        assert notifications[0]["eventType"] == "new_client_request"
    finally:
        cleanup(schema)

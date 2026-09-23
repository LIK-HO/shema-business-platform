import os
import uuid
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from shema_platform.application.commands import Actor
from shema_platform.application.critical_workflows import CommercialActionCreateWorkflow
from shema_platform.domain.identity import Identity, IdentityState
from shema_platform.experience.api import create_app
from shema_platform.experience.api_models import CommercialActionCreateRequest, CommercialActionResponse
from shema_platform.foundation.authentication import AuthenticatedActor, AuthenticationRequired
from shema_platform.foundation.authorization import AuthorizationSubject, Permission, RBACAuthorizer
from shema_platform.foundation.policy import PolicyEngine
from shema_platform.foundation.telemetry import InMemoryTelemetrySink
from shema_platform.platform.migrations import MigrationPlan, MigrationRunner
from shema_platform.platform.postgres import PostgresUnitOfWork
from shema_platform.platform.postgres_repositories import PostgresIdentityRepository

pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("DATABASE_URL is not configured", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]


def make_schema() -> str:
    return "observability_" + uuid.uuid4().hex


def connection(schema: str) -> psycopg.Connection:
    conn = psycopg.connect(DATABASE_URL)
    conn.execute('set search_path to "' + schema + '"')
    conn.commit()
    return conn


def migrate(schema: str) -> None:
    with psycopg.connect(DATABASE_URL) as bootstrap:
        bootstrap.execute('create schema "' + schema + '"')
        bootstrap.commit()

    plan = MigrationPlan.from_directory(ROOT / "db" / "migrations")
    MigrationRunner(lambda: connection(schema), plan).apply()


def seed_identity(schema: str, identity_id: str) -> None:
    with connection(schema) as conn:
        PostgresIdentityRepository(conn).add(
            Identity(
                identity_id,
                "ООО Observability E2E",
                IdentityState.VERIFIED,
                tax_id="7700000002",
            )
        )
        conn.commit()


def cleanup(schema: str) -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute('drop schema "' + schema + '" cascade')
        conn.commit()


class CorrelationAuthenticator:
    def authenticate(self, authorization: str | None) -> AuthenticatedActor:
        if authorization != "Bearer b6-token":
            raise AuthenticationRequired()
        return AuthenticatedActor(
            actor_id="operator-1",
            trust_level=2,
            permissions=frozenset({Permission.COMMERCIAL_ACTION_CREATE}),
        )


class CorrelatedCommercialApplication:
    def __init__(self, workflow: CommercialActionCreateWorkflow) -> None:
        self.workflow = workflow

    def create_commercial_action(
        self,
        request: CommercialActionCreateRequest,
        context,
    ) -> CommercialActionResponse:
        action = self.workflow.execute(
            action_id="action-b6-correlation-1",
            actor=Actor(
                context.actor_id,
                context.trust_level,
                context.permissions,
            ),
            identity_id=request.identity_id,
            contact_ref=request.contact_ref,
            channel=request.channel,
            evidence_refs=tuple(request.evidence_refs),
            request_hash="request:b6:correlation:1",
            idempotency_key=context.idempotency_key or "",
            correlation_id=context.correlation_id,
        )
        return CommercialActionResponse(
            actionId=action.action_id,
            identityId=action.identity_id,
            contactRef=action.contact_ref,
            channel=action.channel,
            status=action.status.value,
        )


def test_http_correlation_reaches_audit_and_telemetry() -> None:
    schema = make_schema()
    correlation_id = "corr-b6-e2e"
    identity_id = str(uuid.uuid4())
    telemetry = InMemoryTelemetrySink()

    try:
        migrate(schema)
        seed_identity(schema, identity_id)

        authorizer = RBACAuthorizer(
            (
                AuthorizationSubject(
                    "operator-1",
                    frozenset({Permission.COMMERCIAL_ACTION_CREATE}),
                ),
            )
        )
        workflow = CommercialActionCreateWorkflow(
            lambda: PostgresUnitOfWork(lambda: connection(schema)),
            authorizer,
            PolicyEngine(),
        )
        application = CorrelatedCommercialApplication(workflow)

        client = TestClient(
            create_app(
                application,
                CorrelationAuthenticator(),
                telemetry=telemetry,
            )
        )

        response = client.post(
            "/v1/commercial-actions",
            headers={
                "Authorization": "Bearer b6-token",
                "Idempotency-Key": "idem-b6-correlation-1",
                "X-Correlation-Id": correlation_id,
            },
            json={
                "identityId": identity_id,
                "contactRef": "chat:b6",
                "channel": "max",
                "evidenceRefs": ["evidence:b6"],
            },
        )

        assert response.status_code == 201
        assert response.headers["X-Correlation-Id"] == correlation_id
        assert response.json()["actionId"] == "action-b6-correlation-1"

        completed_events = [
            event
            for event in telemetry.all()
            if event.name == "http.request.completed"
        ]
        assert len(completed_events) == 1
        event = completed_events[0]
        assert event.correlation_id == correlation_id
        assert event.attributes["status"] == 201
        assert "authorization" not in event.attributes
        assert "body" not in event.attributes

        with connection(schema) as conn:
            audit = conn.execute(
                """
                select correlation_id
                from audit_log
                where action = 'commercial_action.created'
                  and resource_id = %s
                """,
                ("action-b6-correlation-1",),
            ).fetchone()
            assert audit == (correlation_id,)

            assert conn.execute(
                """
                select count(*)
                from idempotency_key
                where key = 'idem-b6-correlation-1'
                """
            ).fetchone() == (1,)

            assert conn.execute(
                """
                select count(*)
                from outbox_event
                where event_type = 'commercial_action.created'
                  and aggregate_id = 'action-b6-correlation-1'
                """
            ).fetchone() == (1,)
    finally:
        cleanup(schema)

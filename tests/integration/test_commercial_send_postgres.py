import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from shema_platform.application.commands import Actor
from shema_platform.application.commercial_execution import CommercialActionSendWorkflow
from shema_platform.application.communication import (
    CommunicationAdapter,
    CommunicationGateway,
    CommunicationSendRequest,
    CommunicationSendResult,
)
from shema_platform.domain.commercial_action import CommercialAction, CommercialActionStatus
from shema_platform.foundation.authorization import (
    AuthorizationSubject,
    Permission,
    RBACAuthorizer,
)
from shema_platform.foundation.policy import PolicyEngine
from shema_platform.platform.postgres import PostgresUnitOfWork

pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("DATABASE_URL is not configured", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]


def apply_migrations(connection: psycopg.Connection) -> None:
    for name in (
        "0001_foundation.sql",
        "0002_discovery.sql",
        "0003_audit_context.sql",
        "0004_commercial_execution.sql",
        "0008_commercial_send_reservation.sql",
    ):
        for statement in (ROOT / "db/migrations" / name).read_text().split(";"):
            statement = statement.strip()
            if statement:
                connection.execute(statement)


class FakeAdapter(CommunicationAdapter):
    channel = "max"

    def send(self, request: CommunicationSendRequest) -> CommunicationSendResult:
        return CommunicationSendResult(
            action_id=request.action_id,
            channel=request.channel,
            external_message_id=f"external:{request.idempotency_key}",
            accepted=True,
        )


def test_postgres_commercial_send_workflow_round_trip() -> None:
    with psycopg.connect(DATABASE_URL) as setup:
        apply_migrations(setup)
        action = CommercialAction(
            action_id=str(uuid4()),
            identity_id="identity:integration",
            contact_ref="chat:integration",
            channel="max",
            evidence_refs=("evidence:integration",),
        ).mark_ready()
        from shema_platform.platform.postgres_repositories import (
            PostgresCommercialActionRepository,
        )

        PostgresCommercialActionRepository(setup).add(action)
        setup.commit()
        def factory() -> PostgresUnitOfWork:
            return PostgresUnitOfWork(
                lambda: psycopg.connect(DATABASE_URL)
            )
        workflow = CommercialActionSendWorkflow(
            factory,
            CommunicationGateway(FakeAdapter()),
            RBACAuthorizer(
                (
                    AuthorizationSubject(
                        "operator-1",
                        frozenset({Permission.COMMERCIAL_ACTION_SEND}),
                    ),
                )
            ),
            PolicyEngine(),
        )

        idempotency_key = f"send:{uuid4()}"
        result = workflow.execute(
            actor=Actor("operator-1", trust_level=2),
            action_id=action.action_id,
            body="Здравствуйте",
            idempotency_key=idempotency_key,
        )
        assert result.accepted

        with factory() as check:
            loaded = check.commercial_actions.get(action.action_id)
            assert loaded is not None
            assert loaded.status.value == "sent"
            assert check.idempotency.get(idempotency_key) is not None
            assert len(check.outbox.pending()) == 1

        with psycopg.connect(DATABASE_URL) as cleanup:
            cleanup.execute(
                "delete from audit_log where resource_id = %s",
                (action.action_id,),
            )
            cleanup.execute(
                "delete from outbox_event where aggregate_id = %s",
                (action.action_id,),
            )
            cleanup.execute(
                "delete from idempotency_key where result_ref = %s",
                (result.external_message_id,),
            )
            cleanup.execute(
                "delete from commercial_action where action_id = %s",
                (action.action_id,),
            )
            cleanup.commit()


def test_postgres_commercial_send_reservation_reclaims_expired_lease() -> None:
    action = CommercialAction(
        action_id=str(uuid4()),
        identity_id="identity:integration",
        contact_ref="chat:integration",
        channel="max",
        evidence_refs=("evidence:integration",),
    ).mark_ready()

    with psycopg.connect(DATABASE_URL) as first, psycopg.connect(DATABASE_URL) as second:
        apply_migrations(first)
        from shema_platform.platform.postgres_repositories import PostgresCommercialActionRepository

        repository = PostgresCommercialActionRepository(first)
        repository.add(action)
        first.commit()

        start = datetime.now(UTC)
        claimed = repository.claim_for_send(
            action.action_id,
            "worker-1",
            lease_until=start + timedelta(seconds=1),
            now=start,
        )
        assert claimed.status is CommercialActionStatus.SENDING
        assert claimed.send_attempt == 1
        first.commit()

        second_repository = PostgresCommercialActionRepository(second)
        reclaimed = second_repository.claim_for_send(
            action.action_id,
            "worker-2",
            lease_until=start + timedelta(seconds=60),
            now=start + timedelta(seconds=2),
        )
        assert reclaimed.status is CommercialActionStatus.SENDING
        assert reclaimed.send_attempt == 2
        assert reclaimed.send_worker_id == "worker-2"
        second.commit()

        first.execute(
            "delete from commercial_action where action_id = %s",
            (action.action_id,),
        )
        first.commit()

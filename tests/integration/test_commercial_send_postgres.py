import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from shema_platform.application.commercial_execution import CommercialActionSendWorkflow
from shema_platform.application.communication import (
    CommunicationAdapter,
    CommunicationGateway,
    CommunicationSendRequest,
    CommunicationSendResult,
)
from shema_platform.domain.commercial_action import CommercialAction
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

        factory = lambda: PostgresUnitOfWork(lambda: psycopg.connect(DATABASE_URL))
        workflow = CommercialActionSendWorkflow(
            factory,
            CommunicationGateway(FakeAdapter()),
        )

        result = workflow.execute(
            action_id=action.action_id,
            body="Здравствуйте",
            idempotency_key=f"send:{uuid4()}",
        )
        assert result.accepted

        with factory() as check:
            loaded = check.commercial_actions.get(action.action_id)
            assert loaded is not None
            assert loaded.status.value == "sent"
            assert check.idempotency.get(result.external_message_id.replace("external:", "send:")) is not None
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

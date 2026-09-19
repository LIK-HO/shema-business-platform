import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from shema_platform.foundation.errors import IntegrityViolation
from shema_platform.foundation.outbox import OutboxEvent, OutboxStatus
from shema_platform.platform.postgres_repositories import PostgresOutboxRepository

pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("DATABASE_URL is not configured", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]


def apply_migration(connection: psycopg.Connection, path: Path) -> None:
    statements = [
        statement.strip()
        for statement in path.read_text().split(";")
        if statement.strip()
    ]
    for statement in statements:
        connection.execute(statement)


def prepare_database(connection: psycopg.Connection) -> None:
    for migration in (
        "0001_foundation.sql",
        "0002_discovery.sql",
        "0003_audit_context.sql",
        "0004_commercial_execution.sql",
        "0005_ai_run.sql",
        "0006_job_execution.sql",
        "0007_outbox_delivery_lease.sql",
    ):
        apply_migration(connection, ROOT / "db/migrations" / migration)


def make_event() -> OutboxEvent:
    return OutboxEvent(
        event_id=str(uuid4()),
        event_type="job.completed",
        aggregate_type="job",
        aggregate_id=str(uuid4()),
        payload={"state": "succeeded"},
        occurred_at=datetime.now(UTC),
    )


def test_outbox_delivery_is_lease_safe_and_reclaimable() -> None:
    event = make_event()

    with psycopg.connect(DATABASE_URL) as first, psycopg.connect(DATABASE_URL) as second:
        prepare_database(first)
        first.commit()

        first_repo = PostgresOutboxRepository(first)
        second_repo = PostgresOutboxRepository(second)
        first_repo.append(event)
        first.commit()

        start = datetime.now(UTC)
        claimed = first_repo.claim_pending(
            "worker-1",
            lease_seconds=10,
            now=start,
            limit=1,
        )
        assert len(claimed) == 1
        assert claimed[0].attempt == 1
        assert claimed[0].worker_id == "worker-1"
        first.commit()

        blocked = second_repo.claim_pending(
            "worker-2",
            lease_seconds=10,
            now=start + timedelta(seconds=1),
            limit=1,
        )
        assert blocked == ()

        with pytest.raises(IntegrityViolation, match="missing or expired"):
            second_repo.mark_published(
                event.event_id,
                "worker-2",
                now=start + timedelta(seconds=2),
            )

        reclaimed = second_repo.claim_pending(
            "worker-2",
            lease_seconds=10,
            now=start + timedelta(seconds=10),
            limit=1,
        )
        assert len(reclaimed) == 1
        assert reclaimed[0].attempt == 2
        assert reclaimed[0].worker_id == "worker-2"
        second.commit()

        with pytest.raises(IntegrityViolation, match="missing or expired"):
            first_repo.mark_published(
                event.event_id,
                "worker-1",
                now=start + timedelta(seconds=10),
            )

        published = second_repo.mark_published(
            event.event_id,
            "worker-2",
            now=start + timedelta(seconds=11),
        )
        assert published.status is OutboxStatus.PUBLISHED

        assert event.event_id not in {
            item.event_id for item in second_repo.pending()
        }

        first.execute("delete from outbox_event where event_id = %s", (event.event_id,))
        first.commit()

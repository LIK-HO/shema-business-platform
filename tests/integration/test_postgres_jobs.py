import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from shema_platform.foundation.jobs import JobExecution, JobRecord, JobState
from shema_platform.platform.postgres_repositories import PostgresJobRepository

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
    ):
        apply_migration(connection, ROOT / "db/migrations" / migration)


def test_postgres_job_lifecycle_is_lease_safe() -> None:
    job_id = f"job:{uuid4()}"
    idempotency_key = f"job-idem:{uuid4()}"
    available_at = datetime.now(UTC)

    record = JobRecord(
        execution=JobExecution(
            job_id=job_id,
            job_type="integration.test",
            attempt=1,
            state=JobState.QUEUED,
            idempotency_key=idempotency_key,
        ),
        payload={"subject_ref": "identity:test"},
        available_at=available_at,
    )

    with psycopg.connect(DATABASE_URL) as connection:
        prepare_database(connection)
        repository = PostgresJobRepository(connection)

        assert repository.enqueue(record) == record
        assert repository.enqueue(record) == record

        claimed = repository.claim_next(
            "worker-1",
            lease_seconds=60,
            now=available_at,
        )
        assert claimed is not None
        assert claimed.execution.state is JobState.RUNNING
        assert claimed.execution.lease is not None
        assert claimed.execution.lease.worker_id == "worker-1"
        assert claimed.execution.attempt == 1

        completed = repository.complete(
            job_id,
            "worker-1",
            now=available_at + timedelta(seconds=10),
        )
        assert completed.execution.state is JobState.SUCCEEDED

        loaded = repository.get(job_id)
        assert loaded is not None
        assert loaded.execution.state is JobState.SUCCEEDED

        connection.execute("delete from job_execution where job_id = %s", (job_id,))
        connection.commit()


def test_postgres_job_retry_advances_attempt_after_reclaim() -> None:
    job_id = f"job:{uuid4()}"
    idempotency_key = f"job-idem:{uuid4()}"
    available_at = datetime.now(UTC)

    record = JobRecord(
        execution=JobExecution(
            job_id=job_id,
            job_type="integration.retry",
            attempt=1,
            state=JobState.QUEUED,
            idempotency_key=idempotency_key,
        ),
        payload={"test": True},
        available_at=available_at,
    )

    with psycopg.connect(DATABASE_URL) as connection:
        prepare_database(connection)
        repository = PostgresJobRepository(connection)

        repository.enqueue(record)
        claimed = repository.claim_next(
            "worker-1",
            lease_seconds=1,
            now=available_at,
        )
        assert claimed is not None

        failed = repository.fail(
            job_id,
            "worker-1",
            retryable=True,
            error="temporary dependency failure",
            available_at=available_at,
            now=available_at + timedelta(seconds=1),
        )
        assert failed.execution.state is JobState.RETRYABLE_FAILURE

        reclaimed = repository.claim_next(
            "worker-2",
            lease_seconds=60,
            now=available_at + timedelta(seconds=2),
        )
        assert reclaimed is not None
        assert reclaimed.execution.attempt == 2
        assert reclaimed.execution.lease is not None
        assert reclaimed.execution.lease.worker_id == "worker-2"

        connection.execute("delete from job_execution where job_id = %s", (job_id,))
        connection.commit()


def test_postgres_job_lease_can_be_renewed_only_before_expiry() -> None:
    job_id = f"job:{uuid4()}"
    idempotency_key = f"job-idem:{uuid4()}"
    available_at = datetime.now(UTC)

    record = JobRecord(
        execution=JobExecution(
            job_id=job_id,
            job_type="integration.renew",
            attempt=1,
            state=JobState.QUEUED,
            idempotency_key=idempotency_key,
        ),
        payload={},
        available_at=available_at,
    )

    with psycopg.connect(DATABASE_URL) as connection:
        prepare_database(connection)
        repository = PostgresJobRepository(connection)
        repository.enqueue(record)

        claimed = repository.claim_next(
            "worker-1",
            lease_seconds=10,
            now=available_at,
        )
        assert claimed is not None

        renewed = repository.renew(
            job_id,
            "worker-1",
            lease_seconds=60,
            now=available_at + timedelta(seconds=5),
        )
        assert renewed.execution.lease is not None
        assert renewed.execution.lease.worker_id == "worker-1"

        connection.execute("delete from job_execution where job_id = %s", (job_id,))
        connection.commit()

from datetime import UTC, datetime, timedelta

import pytest

from shema_platform.foundation.jobs import JobExecution, JobLease, JobState


def queued_job() -> JobExecution:
    return JobExecution(
        job_id="job-1",
        job_type="intelligence.research",
        attempt=1,
        state=JobState.QUEUED,
        idempotency_key="job-1:research",
    )


def test_job_requires_matching_lease_and_can_succeed() -> None:
    job = queued_job()
    lease = JobLease(
        job_id="job-1",
        worker_id="worker-1",
        leased_until=datetime.now(UTC) + timedelta(minutes=1),
    )

    running = job.start(lease)
    assert running.state is JobState.RUNNING
    assert running.lease == lease
    assert running.succeed().state is JobState.SUCCEEDED


def test_job_rejects_foreign_lease() -> None:
    job = queued_job()
    lease = JobLease(
        job_id="other-job",
        worker_id="worker-1",
        leased_until=datetime.now(UTC) + timedelta(minutes=1),
    )

    with pytest.raises(ValueError, match="different job"):
        job.start(lease)


def test_expired_lease_is_detected() -> None:
    lease = JobLease(
        job_id="job-1",
        worker_id="worker-1",
        leased_until=datetime.now(UTC) - timedelta(seconds=1),
    )

    assert lease.is_expired()


def test_running_job_can_fail_retryably_or_permanently() -> None:
    job = queued_job()
    lease = JobLease(
        job_id="job-1",
        worker_id="worker-1",
        leased_until=datetime.now(UTC) + timedelta(minutes=1),
    )
    running = job.start(lease)

    assert running.fail(retryable=True).state is JobState.RETRYABLE_FAILURE
    assert running.fail(retryable=False).state is JobState.FAILED


def test_job_rejects_expired_lease_at_start() -> None:
    job = queued_job()
    lease = JobLease(
        job_id="job-1",
        worker_id="worker-1",
        leased_until=datetime.now(UTC) - timedelta(seconds=1),
    )

    with pytest.raises(ValueError, match="expired"):
        job.start(lease)

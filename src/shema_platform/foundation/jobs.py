from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    RETRYABLE_FAILURE = "retryable_failure"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class JobLease:
    job_id: str
    worker_id: str
    leased_until: datetime

    def is_expired(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(UTC)
        return current >= self.leased_until


@dataclass(frozen=True, slots=True)
class JobExecution:
    job_id: str
    job_type: str
    attempt: int
    state: JobState
    idempotency_key: str
    lease: JobLease | None = None

    def __post_init__(self) -> None:
        if not self.job_id.strip() or not self.job_type.strip():
            raise ValueError("job_id and job_type are required")
        if self.attempt < 1:
            raise ValueError("attempt must be >= 1")
        if not self.idempotency_key.strip():
            raise ValueError("idempotency_key is required")

    def start(self, lease: JobLease) -> JobExecution:
        if lease.job_id != self.job_id:
            raise ValueError("lease belongs to a different job")
        if self.state not in {
            JobState.QUEUED,
            JobState.RETRYABLE_FAILURE,
        }:
            raise ValueError("job cannot be started from current state")
        return JobExecution(
            job_id=self.job_id,
            job_type=self.job_type,
            attempt=self.attempt,
            state=JobState.RUNNING,
            idempotency_key=self.idempotency_key,
            lease=lease,
        )

    def succeed(self) -> JobExecution:
        if self.state is not JobState.RUNNING:
            raise ValueError("only running job can succeed")
        return JobExecution(
            job_id=self.job_id,
            job_type=self.job_type,
            attempt=self.attempt,
            state=JobState.SUCCEEDED,
            idempotency_key=self.idempotency_key,
            lease=self.lease,
        )

    def fail(self, retryable: bool) -> JobExecution:
        if self.state is not JobState.RUNNING:
            raise ValueError("only running job can fail")
        return JobExecution(
            job_id=self.job_id,
            job_type=self.job_type,
            attempt=self.attempt,
            state=JobState.RETRYABLE_FAILURE if retryable else JobState.FAILED,
            idempotency_key=self.idempotency_key,
            lease=self.lease,
        )

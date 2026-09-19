from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType


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

    def __post_init__(self) -> None:
        if not self.job_id.strip() or not self.worker_id.strip():
            raise ValueError("job_id and worker_id are required")
        if self.leased_until.tzinfo is None:
            raise ValueError("leased_until must be timezone-aware")

    def is_expired(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            raise ValueError("now must be timezone-aware")
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
        if self.state is JobState.RUNNING and self.lease is None:
            raise ValueError("running job requires a lease")
        if self.lease is not None and self.lease.job_id != self.job_id:
            raise ValueError("lease belongs to a different job")

    def start(self, lease: JobLease, now: datetime | None = None) -> JobExecution:
        if lease.job_id != self.job_id:
            raise ValueError("lease belongs to a different job")
        if lease.is_expired(now):
            raise ValueError("job lease is already expired")
        if self.state not in {JobState.QUEUED, JobState.RETRYABLE_FAILURE}:
            raise ValueError("job cannot be started from current state")
        return JobExecution(
            job_id=self.job_id,
            job_type=self.job_type,
            attempt=self.attempt,
            state=JobState.RUNNING,
            idempotency_key=self.idempotency_key,
            lease=lease,
        )

    def succeed(self, now: datetime | None = None) -> JobExecution:
        self._require_active_lease(now)
        return JobExecution(
            job_id=self.job_id,
            job_type=self.job_type,
            attempt=self.attempt,
            state=JobState.SUCCEEDED,
            idempotency_key=self.idempotency_key,
            lease=self.lease,
        )

    def fail(self, retryable: bool, now: datetime | None = None) -> JobExecution:
        self._require_active_lease(now)
        return JobExecution(
            job_id=self.job_id,
            job_type=self.job_type,
            attempt=self.attempt,
            state=JobState.RETRYABLE_FAILURE if retryable else JobState.FAILED,
            idempotency_key=self.idempotency_key,
            lease=self.lease,
        )

    def _require_active_lease(self, now: datetime | None) -> None:
        if self.state is not JobState.RUNNING or self.lease is None:
            raise ValueError("only running job can complete")
        if self.lease.is_expired(now):
            raise ValueError("job lease has expired")


@dataclass(frozen=True, slots=True)
class JobRecord:
    execution: JobExecution
    payload: Mapping[str, object]
    available_at: datetime
    last_error: str | None = None

    def __post_init__(self) -> None:
        if self.available_at.tzinfo is None:
            raise ValueError("available_at must be timezone-aware")
        if self.last_error is not None and not self.last_error.strip():
            raise ValueError("last_error cannot be blank")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))

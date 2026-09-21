from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from shema_platform.application.ports import UnitOfWork
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.jobs import JobRecord, JobState
from shema_platform.foundation.outbox import OutboxEvent
from shema_platform.foundation.recovery import RetryPolicy


class JobHandlerContext:
    """Narrow execution context exposed to durable job handlers."""

    def __init__(
        self,
        *,
        record: JobRecord,
        worker_id: str,
        renew_callback: Callable[[str, datetime], JobRecord],
    ) -> None:
        if not worker_id.strip():
            raise ValueError("worker_id is required")
        self.record = record
        self.worker_id = worker_id
        self._renew_callback = renew_callback

    def renew_lease(self, *, now: datetime | None = None) -> JobRecord:
        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        renewed = self._renew_callback(self.record.execution.job_id, current)
        self.record = renewed
        return renewed


class JobHandler(Protocol):
    def __call__(
        self,
        context: JobHandlerContext,
    ) -> Mapping[str, object] | None: ...


class RetryableJobError(RuntimeError):
    """Handler failure that should return the job to retryable state."""


class PermanentJobError(RuntimeError):
    """Handler failure that must terminate the job."""


@dataclass(frozen=True, slots=True)
class JobHandlerRegistry:
    handlers: Mapping[str, JobHandler]

    def __post_init__(self) -> None:
        normalized = dict(self.handlers)
        if any(not key.strip() for key in normalized):
            raise ValueError("job handler type cannot be blank")
        object.__setattr__(self, "handlers", normalized)

    def resolve(self, job_type: str) -> JobHandler:
        handler = self.handlers.get(job_type)
        if handler is None:
            raise PermanentJobError(f"no handler registered for job type: {job_type}")
        return handler


@dataclass(frozen=True, slots=True)
class JobRunResult:
    job_id: str
    state: JobState
    attempt: int
    output: Mapping[str, object] | None = None
    error: str | None = None


class JobRunner:
    """At-least-once worker orchestration over the durable JobRepository."""

    def __init__(
        self,
        unit_of_work_factory: Callable[[], UnitOfWork],
        handlers: JobHandlerRegistry,
        retry_policy: RetryPolicy | None = None,
        *,
        lease_seconds: int = 60,
        worker_id: str = "worker",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be > 0")
        if not worker_id.strip():
            raise ValueError("worker_id is required")
        self._unit_of_work_factory = unit_of_work_factory
        self._handlers = handlers
        self._retry_policy = retry_policy or RetryPolicy()
        self._lease_seconds = lease_seconds
        self._worker_id = worker_id
        self._clock = clock or (lambda: datetime.now(UTC))

    def run_next(self, *, now: datetime | None = None) -> JobRunResult | None:
        current = now or self._clock()
        self._validate_time(current)

        with self._unit_of_work_factory() as uow:
            claimed = uow.jobs.claim_next(
                self._worker_id,
                lease_seconds=self._lease_seconds,
                now=current,
            )

        if claimed is None:
            return None

        context = JobHandlerContext(
            record=claimed,
            worker_id=self._worker_id,
            renew_callback=self._renew_lease,
        )

        try:
            handler = self._handlers.resolve(claimed.execution.job_type)
            output = handler(context)
        except RetryableJobError as exc:
            return self._record_failure(
                claimed,
                str(exc),
                retryable=True,
                now=self._clock(),
            )
        except PermanentJobError as exc:
            return self._record_failure(
                claimed,
                str(exc),
                retryable=False,
                now=self._clock(),
            )
        except Exception as exc:
            return self._record_failure(
                claimed,
                f"unexpected handler failure: {exc}",
                retryable=True,
                now=self._clock(),
            )

        completed_at = self._clock()
        self._validate_time(completed_at)
        completed = self._complete(
            claimed.execution.job_id,
            context.worker_id,
            now=completed_at,
            output=output,
        )
        return JobRunResult(
            job_id=completed.execution.job_id,
            state=completed.execution.state,
            attempt=completed.execution.attempt,
            output=output,
        )

    def _renew_lease(self, job_id: str, now: datetime) -> JobRecord:
        with self._unit_of_work_factory() as uow:
            return uow.jobs.renew(
                job_id,
                self._worker_id,
                lease_seconds=self._lease_seconds,
                now=now,
            )

    def _record_failure(
        self,
        claimed: JobRecord,
        error: str,
        *,
        retryable: bool,
        now: datetime,
    ) -> JobRunResult:
        self._validate_time(now)
        attempt = claimed.execution.attempt
        should_retry = retryable and self._retry_policy.is_retryable(attempt)
        available_at = (
            self._retry_policy.next_available_at(attempt, now)
            if should_retry
            else now
        )

        with self._unit_of_work_factory() as uow:
            failed = uow.jobs.fail(
                claimed.execution.job_id,
                self._worker_id,
                retryable=should_retry,
                error=error,
                available_at=available_at,
                now=now,
            )
            event = self._event_for(
                claimed,
                failed.execution.state,
                error=error,
                available_at=available_at,
                occurred_at=now,
            )
            uow.outbox.append(event)
            uow.audits.append(
                self._audit_for(
                    claimed,
                    outcome=failed.execution.state.value,
                    error=error,
                    occurred_at=now,
                )
            )

        return JobRunResult(
            job_id=failed.execution.job_id,
            state=failed.execution.state,
            attempt=failed.execution.attempt,
            error=error,
        )

    def _complete(
        self,
        job_id: str,
        worker_id: str,
        *,
        now: datetime,
        output: Mapping[str, object] | None,
    ) -> JobRecord:
        with self._unit_of_work_factory() as uow:
            completed = uow.jobs.complete(job_id, worker_id, now=now)
            payload = {
                "job_id": job_id,
                "job_type": completed.execution.job_type,
                "attempt": completed.execution.attempt,
                "state": completed.execution.state.value,
            }
            if output is not None:
                payload["output"] = dict(output)
            uow.outbox.append(
                OutboxEvent(
                    event_id=str(
                        uuid5(
                            NAMESPACE_URL,
                            f"job.completed:{job_id}:"
                            f"{completed.execution.attempt}",
                        )
                    ),
                    event_type="job.completed",
                    aggregate_type="job",
                    aggregate_id=job_id,
                    payload=payload,
                    occurred_at=now,
                )
            )
            uow.audits.append(
                AuditRecord(
                    audit_id=str(
                        uuid5(
                            NAMESPACE_URL,
                            f"audit:job.completed:{job_id}:"
                            f"{completed.execution.attempt}",
                        )
                    ),
                    actor_id=worker_id,
                    action="job.completed",
                    resource_type="job",
                    resource_id=job_id,
                    outcome="success",
                    occurred_at=now,
                    metadata={"attempt": completed.execution.attempt},
                )
            )
            return completed

    @staticmethod
    def _event_for(
        claimed: JobRecord,
        state: JobState,
        *,
        error: str,
        available_at: datetime,
        occurred_at: datetime,
    ) -> OutboxEvent:
        event_type = (
            "job.retry_scheduled"
            if state is JobState.RETRYABLE_FAILURE
            else "job.failed"
        )
        return OutboxEvent(
            event_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"{event_type}:{claimed.execution.job_id}:"
                    f"{claimed.execution.attempt}",
                )
            ),
            event_type=event_type,
            aggregate_type="job",
            aggregate_id=claimed.execution.job_id,
            payload={
                "job_id": claimed.execution.job_id,
                "job_type": claimed.execution.job_type,
                "attempt": claimed.execution.attempt,
                "error": error,
                "available_at": available_at.isoformat(),
            },
            occurred_at=occurred_at,
        )

    @staticmethod
    def _audit_for(
        claimed: JobRecord,
        *,
        outcome: str,
        error: str,
        occurred_at: datetime,
    ) -> AuditRecord:
        worker_id = (
            claimed.execution.lease.worker_id
            if claimed.execution.lease
            else "worker"
        )
        return AuditRecord(
            audit_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"audit:job.failure:{claimed.execution.job_id}:"
                    f"{claimed.execution.attempt}",
                )
            ),
            actor_id=worker_id,
            action="job.failure",
            resource_type="job",
            resource_id=claimed.execution.job_id,
            outcome=outcome,
            occurred_at=occurred_at,
            metadata={
                "attempt": claimed.execution.attempt,
                "error": error,
            },
        )

    @staticmethod
    def _validate_time(value: datetime) -> None:
        if value.tzinfo is None:
            raise ValueError("now must be timezone-aware")

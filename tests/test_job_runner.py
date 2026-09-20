from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from shema_platform.application.job_runner import (
    JobHandlerRegistry,
    JobRunner,
    PermanentJobError,
    RetryableJobError,
)
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.jobs import JobExecution, JobLease, JobRecord, JobState
from shema_platform.foundation.observability import InMemoryTelemetry
from shema_platform.foundation.outbox import OutboxEvent
from shema_platform.foundation.recovery import RetryPolicy


class FakeJobs:
    def __init__(self, record: JobRecord) -> None:
        self.record = record

    def enqueue(self, record: JobRecord) -> JobRecord:
        self.record = record
        return record

    def get(self, job_id: str) -> JobRecord | None:
        return self.record if self.record.execution.job_id == job_id else None

    def claim_next(
        self,
        worker_id: str,
        *,
        lease_seconds: int,
        now: datetime,
    ) -> JobRecord | None:
        if self.record.execution.state is not JobState.QUEUED:
            return None
        lease = JobLease(
            job_id=self.record.execution.job_id,
            worker_id=worker_id,
            leased_until=now + timedelta(seconds=lease_seconds),
        )
        running = self.record.execution.start(lease=lease, now=now)
        self.record = JobRecord(
            execution=running,
            payload=self.record.payload,
            available_at=self.record.available_at,
            last_error=self.record.last_error,
        )
        return self.record

    def renew(
        self,
        job_id: str,
        worker_id: str,
        *,
        lease_seconds: int,
        now: datetime,
    ) -> JobRecord:
        if self.record.execution.lease is None:
            raise AssertionError("missing lease")
        renewed_lease = JobLease(
            job_id=job_id,
            worker_id=worker_id,
            leased_until=now + timedelta(seconds=lease_seconds),
        )
        renewed = self.record.execution.renew(renewed_lease, now=now)
        self.record = JobRecord(
            execution=renewed,
            payload=self.record.payload,
            available_at=self.record.available_at,
            last_error=self.record.last_error,
        )
        return self.record

    def complete(self, job_id: str, worker_id: str, *, now: datetime) -> JobRecord:
        self.record = JobRecord(
            execution=self.record.execution.succeed(now),
            payload=self.record.payload,
            available_at=self.record.available_at,
            last_error=None,
        )
        return self.record

    def fail(
        self,
        job_id: str,
        worker_id: str,
        *,
        retryable: bool,
        error: str,
        available_at: datetime,
        now: datetime,
    ) -> JobRecord:
        self.record = JobRecord(
            execution=self.record.execution.fail(retryable, now),
            payload=self.record.payload,
            available_at=available_at,
            last_error=error,
        )
        return self.record


class FakeOutbox:
    def __init__(self) -> None:
        self.events: list[OutboxEvent] = []

    def append(self, event: OutboxEvent) -> OutboxEvent:
        self.events.append(event)
        return event

    def pending(self) -> tuple[OutboxEvent, ...]:
        return tuple(self.events)

    def mark_published(self, event_id: str) -> OutboxEvent:
        raise AssertionError("not needed")


class FakeAudits:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    def append(self, record: AuditRecord) -> None:
        self.records.append(record)


class FakeUoW:
    def __init__(self, jobs: FakeJobs) -> None:
        self.jobs = jobs
        self.outbox = FakeOutbox()
        self.audits = FakeAudits()

    def __enter__(self) -> "FakeUoW":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        return False


def make_uow() -> tuple[FakeUoW, Callable[[], FakeUoW]]:
    now = datetime.now(UTC)
    record = JobRecord(
        execution=JobExecution(
            job_id="job-1",
            job_type="test.job",
            attempt=1,
            state=JobState.QUEUED,
            idempotency_key="job-1",
        ),
        payload={"subject_ref": "identity-1"},
        available_at=now,
    )
    uow = FakeUoW(FakeJobs(record))
    return uow, lambda: uow


def test_job_runner_completes_and_publishes() -> None:
    uow, factory = make_uow()
    telemetry = InMemoryTelemetry()
    runner = JobRunner(
        factory,
        JobHandlerRegistry({"test.job": lambda context: {"ok": True}}),
        worker_id="worker-1",
        telemetry=telemetry,
    )

    result = runner.run_next()

    assert result is not None
    assert result.state is JobState.SUCCEEDED
    assert result.output == {"ok": True}
    assert [event.event_type for event in uow.outbox.events] == ["job.completed"]
    assert [audit.outcome for audit in uow.audits.records] == ["success"]
    assert [event.name for event in telemetry.events] == [
        "job.claimed",
        "job.completed",
    ]


def test_job_handler_can_renew_its_lease_without_database_access() -> None:
    uow, factory = make_uow()
    telemetry = InMemoryTelemetry()
    base = datetime.now(UTC)
    renew_at = base + timedelta(seconds=30)

    def handler(context) -> dict[str, object]:
        assert context.worker_id == "worker-1"
        renewed = context.renew_lease(now=renew_at)
        assert renewed.execution.lease is not None
        assert renewed.execution.lease.leased_until == renew_at + timedelta(
            seconds=60
        )
        assert context.record == renewed
        return {"renewed": True}

    runner = JobRunner(
        factory,
        JobHandlerRegistry({"test.job": handler}),
        lease_seconds=60,
        worker_id="worker-1",
        clock=lambda: renew_at,
        telemetry=telemetry,
    )

    result = runner.run_next(now=base)

    assert result is not None
    assert result.state is JobState.SUCCEEDED
    assert result.output == {"renewed": True}
    assert [event.name for event in telemetry.events] == [
        "job.claimed",
        "job.lease.renewed",
        "job.completed",
    ]


def test_job_runner_schedules_retryable_failure() -> None:
    uow, factory = make_uow()

    def fail(_: object) -> None:
        raise RetryableJobError("temporary")

    runner = JobRunner(
        factory,
        JobHandlerRegistry({"test.job": fail}),
        retry_policy=RetryPolicy(
            max_attempts=3,
            initial_delay_seconds=2,
            max_delay_seconds=10,
        ),
        worker_id="worker-1",
    )

    result = runner.run_next()

    assert result is not None
    assert result.state is JobState.RETRYABLE_FAILURE
    assert result.error == "temporary"
    assert uow.jobs.record.last_error == "temporary"
    assert uow.outbox.events[0].event_type == "job.retry_scheduled"


def test_job_runner_terminates_permanent_failure_and_missing_handler() -> None:
    for registry in (
        JobHandlerRegistry(
            {"test.job": lambda _: (_ for _ in ()).throw(PermanentJobError("bad"))}
        ),
        JobHandlerRegistry({}),
    ):
        uow, factory = make_uow()
        runner = JobRunner(factory, registry, worker_id="worker-1")

        result = runner.run_next()

        assert result is not None
        assert result.state is JobState.FAILED
        assert uow.jobs.record.execution.state is JobState.FAILED
        assert uow.outbox.events[0].event_type == "job.failed"

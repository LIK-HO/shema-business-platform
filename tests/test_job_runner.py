from datetime import UTC, datetime, timedelta

from shema_platform.application.job_runner import (
    JobHandlerRegistry,
    JobRunner,
    PermanentJobError,
    RetryableJobError,
)
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.jobs import JobExecution, JobRecord, JobState
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

    def claim_next(self, worker_id: str, *, lease_seconds: int, now: datetime) -> JobRecord | None:
        if self.record.execution.state is not JobState.QUEUED:
            return None
        lease = self.record.execution.lease
        running = self.record.execution.start(
            lease=type("Lease", (), {
                "job_id": self.record.execution.job_id,
                "worker_id": worker_id,
                "leased_until": now + timedelta(seconds=lease_seconds),
                "is_expired": lambda self, current=None: False,
            })(),
            now=now,
        )
        self.record = JobRecord(
            execution=running,
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


class FakeUoW:
    def __init__(self, jobs: FakeJobs) -> None:
        self.jobs = jobs
        self.outbox_events: list[OutboxEvent] = []
        self.audit_records: list[AuditRecord] = []
        self.outbox = self
        self.audits = self

    def __enter__(self) -> "FakeUoW":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        return False

    def append(self, event: OutboxEvent) -> OutboxEvent:
        self.outbox_events.append(event)
        return event

    def pending(self) -> tuple[OutboxEvent, ...]:
        return tuple(self.outbox_events)

    def mark_published(self, event_id: str) -> OutboxEvent:
        raise AssertionError("not needed")

    def add(self, record: AuditRecord) -> None:
        self.audit_records.append(record)


def make_uow() -> tuple[FakeUoW, callable]:
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
    runner = JobRunner(
        factory,
        JobHandlerRegistry({"test.job": lambda record: {"ok": True}}),
        worker_id="worker-1",
    )

    result = runner.run_next()

    assert result is not None
    assert result.state is JobState.SUCCEEDED
    assert result.output == {"ok": True}
    assert [event.event_type for event in uow.outbox_events] == ["job.completed"]
    assert [audit.outcome for audit in uow.audit_records] == ["success"]


def test_job_runner_schedules_retryable_failure() -> None:
    uow, factory = make_uow()

    def fail(_: JobRecord) -> None:
        raise RetryableJobError("temporary")

    runner = JobRunner(
        factory,
        JobHandlerRegistry({"test.job": fail}),
        retry_policy=RetryPolicy(max_attempts=3, initial_delay_seconds=2, max_delay_seconds=10),
        worker_id="worker-1",
    )

    result = runner.run_next()

    assert result is not None
    assert result.state is JobState.RETRYABLE_FAILURE
    assert result.error == "temporary"
    assert uow.jobs.record.last_error == "temporary"
    assert uow.outbox_events[0].event_type == "job.retry_scheduled"


def test_job_runner_terminates_permanent_failure_and_missing_handler() -> None:
    for registry in (
        JobHandlerRegistry({"test.job": lambda _: (_ for _ in ()).throw(PermanentJobError("bad"))}),
        JobHandlerRegistry({}),
    ):
        uow, factory = make_uow()
        runner = JobRunner(factory, registry, worker_id="worker-1")

        result = runner.run_next()

        assert result is not None
        assert result.state is JobState.FAILED
        assert uow.jobs.record.execution.state is JobState.FAILED
        assert uow.outbox_events[0].event_type == "job.failed"

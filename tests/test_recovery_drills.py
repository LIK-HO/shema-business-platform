from datetime import UTC, datetime, timedelta

from shema_platform.application.job_runner import JobHandlerRegistry, JobRunner, RetryableJobError
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.jobs import JobExecution, JobLease, JobRecord, JobState
from shema_platform.foundation.outbox import OutboxDelivery, OutboxEvent
from shema_platform.foundation.recovery import RetryPolicy


class DrillJobs:
    def __init__(self) -> None:
        self.record = JobRecord(
            execution=JobExecution(
                job_id="job-drill",
                job_type="drill.job",
                attempt=1,
                state=JobState.QUEUED,
                idempotency_key="job-drill",
            ),
            payload={},
            available_at=datetime.now(UTC),
        )

    def claim_next(self, worker_id: str, *, lease_seconds: int, now: datetime):
        if self.record.execution.state in {JobState.QUEUED, JobState.RETRYABLE_FAILURE}:
            lease = JobLease(
                job_id="job-drill",
                worker_id=worker_id,
                leased_until=now + timedelta(seconds=lease_seconds),
            )
            execution = self.record.execution.start(lease, now=now)
            self.record = JobRecord(execution, {}, self.record.available_at)
            return self.record
        return None

    def renew(self, job_id: str, worker_id: str, *, lease_seconds: int, now: datetime):
        raise AssertionError("lease renewal is not used in this drill")

    def complete(self, job_id: str, worker_id: str, *, now: datetime):
        execution = self.record.execution.succeed(now)
        self.record = JobRecord(execution, {}, self.record.available_at)
        return self.record

    def fail(
        self, job_id: str, worker_id: str, *, retryable: bool, error: str,
        available_at: datetime, now: datetime
    ):
        execution = self.record.execution.fail(retryable, now)
        self.record = JobRecord(execution, {}, available_at, error)
        return self.record

    def enqueue(self, record):
        self.record = record
        return record

    def get(self, job_id):
        return self.record if job_id == self.record.execution.job_id else None


class DrillOutbox:
    def __init__(self, event: OutboxEvent) -> None:
        self.events = {event.event_id: event}
        self.leases = {}

    def claim_pending(
        self, worker_id: str, *, lease_seconds: int, now: datetime, limit: int
    ):
        if limit < 1:
            return ()
        event = self.events["event-drill"]
        lease = self.leases.get(event.event_id)
        if event.status.value != "pending":
            return ()
        if lease is not None and lease.lease_until > now:
            return ()
        delivery = OutboxDelivery(
            event=event,
            attempt=(lease.attempt + 1 if lease else 1),
            worker_id=worker_id,
            lease_until=now + timedelta(seconds=lease_seconds),
        )
        self.leases[event.event_id] = delivery
        return (delivery,)

    def mark_published(self, event_id: str, worker_id: str, *, now: datetime):
        delivery = self.leases[event_id]
        assert delivery.worker_id == worker_id
        assert delivery.lease_until > now
        event = self.events[event_id]
        published = OutboxEvent(
            event.event_id,
            event.event_type,
            event.aggregate_type,
            event.aggregate_id,
            event.payload,
            event.occurred_at,
            event.status.__class__.PUBLISHED,
        )
        self.events[event_id] = published
        del self.leases[event_id]
        return published


class DrillUoW:
    def __init__(self, jobs=None, outbox=None):
        self.jobs = jobs
        self.outbox = outbox
        self.audits = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


def test_job_retry_drill_converges_without_duplicate_side_effect() -> None:
    jobs = DrillJobs()
    uow = DrillUoW(jobs=jobs)
    effects = set()
    failed_once = {"value": False}

    def handler(context):
        if context.record.execution.idempotency_key not in effects:
            effects.add(context.record.execution.idempotency_key)
        if not failed_once["value"]:
            failed_once["value"] = True
            raise RetryableJobError("crash after side effect")
        return {"ok": True}

    def factory():
        return uow

    runner = JobRunner(
        factory,
        JobHandlerRegistry({"drill.job": handler}),
        RetryPolicy(max_attempts=3, initial_delay_seconds=1, max_delay_seconds=4),
        worker_id="worker-drill",
    )

    first = runner.run_next(now=datetime.now(UTC))
    assert first is not None
    assert first.state is JobState.RETRYABLE_FAILURE

    second = runner.run_next(now=datetime.now(UTC))
    assert second is not None
    assert second.state is JobState.SUCCEEDED
    assert effects == {"job-drill"}


def test_outbox_publish_crash_drill_reclaims_same_event() -> None:
    event = OutboxEvent(
        event_id="event-drill",
        event_type="drill.completed",
        aggregate_type="drill",
        aggregate_id="1",
        payload={"ok": True},
        occurred_at=datetime.now(UTC),
    )
    outbox = DrillOutbox(event)
    first_side_effects = []
    second_side_effects = []

    start = datetime.now(UTC)
    first_claim = outbox.claim_pending(
        "worker-1", lease_seconds=10, now=start, limit=1
    )[0]
    first_side_effects.append(first_claim.event.event_id)

    reclaimed = outbox.claim_pending(
        "worker-2", lease_seconds=10, now=start + timedelta(seconds=10), limit=1
    )[0]
    second_side_effects.append(reclaimed.event.event_id)

    assert first_side_effects == second_side_effects
    assert reclaimed.attempt == 2
    published = outbox.mark_published(
        event.event_id, "worker-2", now=start + timedelta(seconds=11)
    )
    assert published.status.value == "published"

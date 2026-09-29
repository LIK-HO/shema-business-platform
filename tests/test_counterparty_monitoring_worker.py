from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import Lock
from time import sleep

from shema_platform.application.counterparty_check import (
    CounterpartyIdentifierType,
    CounterpartyObservation,
    SourceReliability,
)
from shema_platform.application.counterparty_monitoring import (
    CounterpartyMonitoringService,
    MonitoringStatus,
)
from shema_platform.application.counterparty_monitoring_worker import (
    BatchItemState,
    BatchStatus,
    CounterpartyMonitoringBatch,
    CounterpartyMonitoringBatchItem,
    CounterpartyMonitoringProviderError,
    CounterpartyMonitoringWorker,
)
from shema_platform.foundation.authorization import Permission
from shema_platform.foundation.idempotency import IdempotencyRecord

NOW = datetime(2026, 9, 29, 14, tzinfo=UTC)
PERMISSIONS = frozenset({Permission.COUNTERPARTY_MONITOR_MANAGE})


class Idempotency:
    def __init__(self):
        self.records = {}

    def reserve(self, key, request_hash, result_ref):
        current = self.records.get(key)
        if current is not None:
            if current.request_hash != request_hash:
                raise AssertionError("idempotency hash mismatch")
            return current
        current = IdempotencyRecord(key, request_hash, result_ref)
        self.records[key] = current
        return current

    def complete(self, key, request_hash, result_ref):
        current = self.records[key]
        if current.request_hash != request_hash:
            raise AssertionError("idempotency hash mismatch")
        self.records[key] = IdempotencyRecord(key, request_hash, result_ref)
        return self.records[key]


class Audit:
    def append(self, record):
        return record


class Outbox:
    def append(self, event):
        return event


class MonitoringRepo:
    def __init__(self):
        self.monitors = {}
        self.snapshots = {}
        self.changes = []

    def add_monitor(self, monitor):
        self.monitors[monitor.monitor_id] = monitor

    def get_monitor(self, monitor_id):
        return self.monitors.get(monitor_id)

    def get_monitor_for_actor(self, monitor_id, actor_id):
        monitor = self.monitors.get(monitor_id)
        return monitor if monitor and monitor.actor_id == actor_id else None

    def list_monitors(self, actor_id):
        return tuple(
            item for item in self.monitors.values() if item.actor_id == actor_id
        )

    def add_favorite(self, favorite):
        return favorite

    def get_favorite(self, favorite_id):
        return None

    def list_favorites(self, actor_id):
        return ()

    def get_latest_snapshot(self, monitor_id):
        items = [
            item for item in self.snapshots.values() if item.monitor_id == monitor_id
        ]
        return max(items, key=lambda item: (item.observed_at, item.snapshot_id), default=None)

    def get_snapshot(self, snapshot_id):
        return self.snapshots.get(snapshot_id)

    def add_snapshot(self, snapshot):
        existing = self.get_snapshot(snapshot.snapshot_id)
        if existing is not None:
            return existing
        self.snapshots[snapshot.snapshot_id] = snapshot
        return snapshot

    def set_last_snapshot(self, monitor_id, *, snapshot_id, checked_at, next_check_at):
        self.monitors[monitor_id] = replace(
            self.monitors[monitor_id],
            last_snapshot_id=snapshot_id,
            last_checked_at=checked_at,
            next_check_at=next_check_at,
            last_error_code=None,
            last_error_at=None,
            updated_at=checked_at,
        )

    def add_change_event(self, event):
        self.changes.append(event)


class BatchRepo:
    def __init__(self, monitoring):
        self.monitoring = monitoring
        self.batches = {}
        self.items = {}
        self._counter = 0

    def start_or_resume_daily_batch(self, *, batch_key, scheduled_at):
        existing = next(
            (batch for batch in self.batches.values() if batch.batch_key == batch_key),
            None,
        )
        if existing:
            return existing
        self._counter += 1
        batch = CounterpartyMonitoringBatch(
            batch_id=f"batch-{self._counter}",
            batch_key=batch_key,
            scheduled_at=scheduled_at,
            status=BatchStatus.COLLECTING,
            next_cursor=None,
            collection_complete=False,
            created_at=scheduled_at,
            completed_at=None,
        )
        self.batches[batch.batch_id] = batch
        return batch

    def materialize_due_items(self, batch_id, *, scheduled_at, limit):
        batch = self.batches[batch_id]
        if batch.collection_complete:
            return batch
        monitors = sorted(
            (
                item
                for item in self.monitoring.monitors.values()
                if item.status is MonitoringStatus.ACTIVE
                and item.next_check_at <= scheduled_at
                and (
                    batch.next_cursor is None
                    or item.monitor_id > batch.next_cursor
                )
            ),
            key=lambda item: item.monitor_id,
        )
        page = monitors[:limit]
        cursor = page[-1].monitor_id if page else batch.next_cursor
        for monitor in page:
            self.items.setdefault(
                (batch_id, monitor.monitor_id),
                CounterpartyMonitoringBatchItem(
                    batch_id=batch_id,
                    monitor_id=monitor.monitor_id,
                    state=BatchItemState.PENDING,
                    attempt=0,
                    available_at=scheduled_at,
                    lease_worker_id=None,
                    lease_until=None,
                    last_error_code=None,
                    last_error_at=None,
                    completed_at=None,
                ),
            )
        complete = len(page) < limit
        batch = replace(
            batch,
            next_cursor=cursor,
            collection_complete=complete,
            status=BatchStatus.RUNNING,
        )
        self.batches[batch_id] = batch
        return batch

    def claim_items(self, batch_id, worker_id, *, lease_seconds, now, limit):
        candidates = []
        for key, item in self.items.items():
            if key[0] != batch_id or item.available_at > now:
                continue
            if item.state in {BatchItemState.PENDING, BatchItemState.RETRYABLE}:
                candidates.append(item)
            elif (
                item.state is BatchItemState.RUNNING
                and item.lease_until is not None
                and item.lease_until < now
            ):
                candidates.append(item)
        candidates = sorted(candidates, key=lambda item: item.monitor_id)[:limit]
        result = []
        for item in candidates:
            updated = replace(
                item,
                state=BatchItemState.RUNNING,
                attempt=item.attempt + 1,
                lease_worker_id=worker_id,
                lease_until=now + timedelta(seconds=lease_seconds),
                last_error_code=None,
                last_error_at=None,
            )
            self.items[(batch_id, item.monitor_id)] = updated
            result.append(updated)
        return tuple(result)

    def complete_item(self, batch_id, monitor_id, worker_id, *, now):
        item = self.items[(batch_id, monitor_id)]
        assert item.state is BatchItemState.RUNNING
        assert item.lease_worker_id == worker_id
        result = replace(
            item,
            state=BatchItemState.COMPLETED,
            lease_worker_id=None,
            lease_until=None,
            completed_at=now,
        )
        self.items[(batch_id, monitor_id)] = result
        return result

    def fail_item(
        self,
        batch_id,
        monitor_id,
        worker_id,
        *,
        retryable,
        error_code,
        available_at,
        now,
    ):
        item = self.items[(batch_id, monitor_id)]
        result = replace(
            item,
            state=BatchItemState.RETRYABLE if retryable else BatchItemState.FAILED,
            available_at=available_at,
            lease_worker_id=None,
            lease_until=None,
            last_error_code=error_code,
            last_error_at=now,
            completed_at=now if not retryable else None,
        )
        self.items[(batch_id, monitor_id)] = result
        return result

    def set_monitor_error(self, monitor_id, *, error_code, now, next_check_at):
        self.monitoring.monitors[monitor_id] = replace(
            self.monitoring.monitors[monitor_id],
            last_error_code=error_code,
            last_error_at=now,
            next_check_at=next_check_at,
            updated_at=now,
        )

    def finalize_batch(self, batch_id, *, now):
        batch = self.batches[batch_id]
        active = any(
            item.batch_id == batch_id
            and item.state in {
                BatchItemState.PENDING,
                BatchItemState.RUNNING,
                BatchItemState.RETRYABLE,
            }
            for item in self.items.values()
        )
        result = replace(
            batch,
            status=(
                BatchStatus.COMPLETED
                if batch.collection_complete and not active
                else BatchStatus.RUNNING
            ),
            completed_at=now if batch.collection_complete and not active else None,
        )
        self.batches[batch_id] = result
        return result


class UOW:
    def __init__(self, monitoring, batches, idempotency, audits, outbox):
        self.monitoring = monitoring
        self.counterparty_monitoring_batches = batches
        self.idempotency = idempotency
        self.audits = audits
        self.outbox = outbox

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


def make_monitoring():
    monitoring = MonitoringRepo()
    batches = BatchRepo(monitoring)

    idempotency = Idempotency()
    audits = Audit()
    outbox = Outbox()

    def factory():
        return UOW(monitoring, batches, idempotency, audits, outbox)

    service = CounterpartyMonitoringService(factory)
    return monitoring, batches, factory, service


def observation(name="ООО \"Пример\"", *, now=NOW):
    return CounterpartyObservation(
        identifier_type=CounterpartyIdentifierType.INN,
        identifier="7707083893",
        canonical_name=name,
        tax_id="7707083893",
        registration_id="1027700132195",
        legal_status="ACTIVE",
        source_ref="https://pb.nalog.ru/",
        source_reliability=SourceReliability.AUTHORITATIVE,
        claim_confidence=1.0,
        observed_at=now,
        expires_at=now + timedelta(days=1),
    )


class ScriptedProvider:
    def __init__(self, values):
        self.values = list(values)
        self.calls = 0

    def observe(self, monitor, *, now):
        value = self.values[min(self.calls, len(self.values) - 1)]
        self.calls += 1
        if isinstance(value, Exception):
            raise value
        return value


def worker_for(provider, factory):
    return CounterpartyMonitoringWorker(
        factory,
        provider,
        worker_id="monitor-worker-1",
        permissions=PERMISSIONS,
        max_parallelism=2,
        lease_seconds=60,
        max_attempts=3,
        backoff_seconds=1,
        max_backoff_seconds=8,
        materialization_limit=100,
        clock=lambda: NOW,
    )


def test_provider_outage_is_checkpointed_without_false_change_and_recovers():
    monitoring, batches, factory, service = make_monitoring()
    monitor = service.save_monitoring(
        identifier_type=CounterpartyIdentifierType.INN,
        identifier="7707083893",
        actor_id="operator-1",
        permissions=PERMISSIONS,
        idempotency_key="monitor-outage",
        correlation_id="corr-outage",
        now=NOW,
    )
    provider = ScriptedProvider(
        [
            CounterpartyMonitoringProviderError(
                "PROVIDER_UNAVAILABLE",
                "registry unavailable",
                retryable=True,
            ),
            observation(now=NOW + timedelta(seconds=2)),
        ]
    )
    worker = worker_for(provider, factory)

    first = worker.run_once(scheduled_at=NOW, batch_key="daily-2026-09-29")
    assert first.batch_status is BatchStatus.RUNNING
    assert first.retryable == 1
    assert monitoring.get_latest_snapshot(monitor.monitor_id) is None
    assert monitoring.monitors[monitor.monitor_id].last_error_code == "PROVIDER_UNAVAILABLE"

    later_worker = CounterpartyMonitoringWorker(
        factory,
        provider,
        worker_id="monitor-worker-2",
        permissions=PERMISSIONS,
        max_parallelism=2,
        lease_seconds=60,
        max_attempts=3,
        backoff_seconds=1,
        max_backoff_seconds=8,
        materialization_limit=100,
        clock=lambda: NOW + timedelta(seconds=2),
    )
    second = later_worker.run_once(
        scheduled_at=NOW + timedelta(seconds=2),
        batch_key="daily-2026-09-29",
    )
    assert second.completed == 1
    assert second.batch_status is BatchStatus.COMPLETED
    assert monitoring.get_latest_snapshot(monitor.monitor_id) is not None
    assert monitoring.changes == []

    duplicate = later_worker.run_once(
        scheduled_at=NOW + timedelta(seconds=2),
        batch_key="daily-2026-09-29",
    )
    assert duplicate.claimed == 0
    assert provider.calls == 2


def test_duplicate_processing_after_worker_crash_is_idempotent():
    monitoring, batches, factory, service = make_monitoring()
    monitor = service.save_monitoring(
        identifier_type=CounterpartyIdentifierType.INN,
        identifier="7707083893",
        actor_id="operator-1",
        permissions=PERMISSIONS,
        idempotency_key="monitor-crash",
        correlation_id="corr-crash",
        now=NOW,
    )
    provider = ScriptedProvider([observation()])
    worker = worker_for(provider, factory)
    summary = worker.run_once(scheduled_at=NOW, batch_key="daily-crash")
    assert summary.completed == 1
    first_snapshot = monitoring.get_latest_snapshot(monitor.monitor_id)
    assert first_snapshot is not None

    item = batches.items[(summary.batch_id, monitor.monitor_id)]
    batches.items[(summary.batch_id, monitor.monitor_id)] = replace(
        item,
        state=BatchItemState.RUNNING,
        lease_worker_id="dead-worker",
        lease_until=NOW - timedelta(seconds=1),
    )
    provider.calls = 0
    replay = CounterpartyMonitoringWorker(
        factory,
        provider,
        worker_id="recovery-worker",
        permissions=PERMISSIONS,
        max_parallelism=1,
        lease_seconds=60,
        max_attempts=3,
        backoff_seconds=1,
        max_backoff_seconds=8,
        materialization_limit=100,
        clock=lambda: NOW,
    )
    replay_result = replay.run_once(
        scheduled_at=NOW,
        batch_key="daily-crash",
    )
    assert replay_result.completed == 1
    assert monitoring.get_latest_snapshot(monitor.monitor_id) == first_snapshot
    assert provider.calls == 1


def test_worker_does_not_call_provider_after_max_attempts() -> None:
    _, batches, factory, service = make_monitoring()
    monitor = service.save_monitoring(
        identifier_type=CounterpartyIdentifierType.INN,
        identifier="7707083893",
        actor_id="operator-1",
        permissions=PERMISSIONS,
        idempotency_key="monitor-max-attempts",
        correlation_id="corr-max-attempts",
        now=NOW,
    )
    batches, _, _, _ = make_monitoring()
    # The test uses a direct claimed item to prove the fail-closed admission gate.
    monitoring, batches, factory, service = make_monitoring()
    monitor = service.save_monitoring(
        identifier_type=CounterpartyIdentifierType.INN,
        identifier="7707083893",
        actor_id="operator-1",
        permissions=PERMISSIONS,
        idempotency_key="monitor-max-attempts-2",
        correlation_id="corr-max-attempts-2",
        now=NOW,
    )
    provider = ScriptedProvider([observation()])
    worker = CounterpartyMonitoringWorker(
        factory,
        provider,
        worker_id="worker-max",
        permissions=PERMISSIONS,
        max_parallelism=1,
        lease_seconds=60,
        max_attempts=1,
        backoff_seconds=1,
        max_backoff_seconds=8,
        materialization_limit=100,
        clock=lambda: NOW,
    )
    first = worker.run_once(scheduled_at=NOW, batch_key="daily-max-attempts")
    assert first.completed == 1
    item = batches.items[(first.batch_id, monitor.monitor_id)]
    batches.items[(first.batch_id, monitor.monitor_id)] = replace(
        item,
        state=BatchItemState.RUNNING,
        lease_worker_id="dead-worker",
        lease_until=NOW - timedelta(seconds=1),
        attempt=1,
    )
    provider.calls = 0
    replay = worker.run_once(scheduled_at=NOW, batch_key="daily-max-attempts")
    assert replay.completed == 0
    assert replay.failed == 1
    assert provider.calls == 0


def test_worker_bounds_provider_parallelism():
    monitoring, _, factory, service = make_monitoring()
    service.save_monitoring(
        identifier_type=CounterpartyIdentifierType.INN,
        identifier="7707083893",
        actor_id="operator-1",
        permissions=PERMISSIONS,
        idempotency_key="monitor-parallel-1",
        correlation_id="corr-parallel-1",
        now=NOW,
    )
    service.save_monitoring(
        identifier_type=CounterpartyIdentifierType.INN,
        identifier="7707083893",
        actor_id="operator-2",
        permissions=PERMISSIONS,
        idempotency_key="monitor-parallel-2",
        correlation_id="corr-parallel-2",
        now=NOW,
    )

    lock = Lock()
    active = 0
    maximum = 0

    class ParallelProvider:
        def observe(self, monitor, *, now):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            sleep(0.02)
            with lock:
                active -= 1
            return observation()

    worker = worker_for(ParallelProvider(), factory)
    result = worker.run_once(scheduled_at=NOW, batch_key="daily-parallel")
    assert result.completed == 2
    assert maximum == 2

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from shema_platform.application.counterparty_check import CounterpartyObservation
from shema_platform.application.counterparty_monitoring import (
    CounterpartyMonitor,
    CounterpartyMonitoringService,
)
from shema_platform.foundation.errors import IntegrityViolation
from shema_platform.foundation.safe_errors import safe_error_detail


class BatchStatus(StrEnum):
    COLLECTING = "collecting"
    RUNNING = "running"
    COMPLETED = "completed"


class BatchItemState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    RETRYABLE = "retryable"
    COMPLETED = "completed"
    FAILED = "failed"


class CounterpartyMonitoringProviderError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class CounterpartyMonitoringProvider(Protocol):
    def observe(
        self,
        monitor: CounterpartyMonitor,
        *,
        now: datetime,
    ) -> CounterpartyObservation: ...


@dataclass(frozen=True, slots=True)
class CounterpartyMonitoringBatch:
    batch_id: str
    batch_key: str
    scheduled_at: datetime
    status: BatchStatus
    next_cursor: str | None
    collection_complete: bool
    created_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class CounterpartyMonitoringBatchItem:
    batch_id: str
    monitor_id: str
    state: BatchItemState
    attempt: int
    available_at: datetime
    lease_worker_id: str | None
    lease_until: datetime | None
    last_error_code: str | None
    last_error_at: datetime | None
    completed_at: datetime | None


class CounterpartyMonitoringBatchRepository(Protocol):
    def start_or_resume_daily_batch(
        self,
        *,
        batch_key: str,
        scheduled_at: datetime,
    ) -> CounterpartyMonitoringBatch: ...

    def materialize_due_items(
        self,
        batch_id: str,
        *,
        scheduled_at: datetime,
        limit: int,
    ) -> CounterpartyMonitoringBatch: ...

    def claim_items(
        self,
        batch_id: str,
        worker_id: str,
        *,
        lease_seconds: int,
        now: datetime,
        limit: int,
    ) -> tuple[CounterpartyMonitoringBatchItem, ...]: ...

    def complete_item(
        self,
        batch_id: str,
        monitor_id: str,
        worker_id: str,
        *,
        now: datetime,
    ) -> CounterpartyMonitoringBatchItem: ...

    def fail_item(
        self,
        batch_id: str,
        monitor_id: str,
        worker_id: str,
        *,
        retryable: bool,
        error_code: str,
        available_at: datetime,
        now: datetime,
    ) -> CounterpartyMonitoringBatchItem: ...

    def set_monitor_error(
        self,
        monitor_id: str,
        *,
        error_code: str,
        now: datetime,
        next_check_at: datetime,
    ) -> None: ...

    def finalize_batch(
        self,
        batch_id: str,
        *,
        now: datetime,
    ) -> CounterpartyMonitoringBatch: ...

    def get_batch(self, batch_id: str) -> CounterpartyMonitoringBatch | None: ...


@dataclass(frozen=True, slots=True)
class CounterpartyMonitoringRunSummary:
    batch_id: str
    batch_status: BatchStatus
    claimed: int
    completed: int
    retryable: int
    failed: int
    collection_complete: bool


class CounterpartyMonitoringWorker:
    """Checkpointed daily monitor worker with bounded concurrency and recovery."""

    def __init__(
        self,
        unit_of_work_factory: Callable,
        provider: CounterpartyMonitoringProvider,
        *,
        worker_id: str,
        permissions,
        max_parallelism: int = 4,
        lease_seconds: int = 120,
        max_attempts: int = 3,
        backoff_seconds: float = 5.0,
        max_backoff_seconds: float = 300.0,
        materialization_limit: int = 100,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not worker_id.strip():
            raise ValueError("worker_id is required")
        if max_parallelism < 1 or max_parallelism > 16:
            raise ValueError("max_parallelism must be between 1 and 16")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        if max_attempts < 1 or max_attempts > 5:
            raise ValueError("max_attempts must be between 1 and 5")
        if backoff_seconds < 0:
            raise ValueError("backoff_seconds cannot be negative")
        if max_backoff_seconds < backoff_seconds:
            raise ValueError("max_backoff_seconds must be >= backoff_seconds")
        if materialization_limit < 1 or materialization_limit > 1000:
            raise ValueError("materialization_limit must be between 1 and 1000")
        self._unit_of_work_factory = unit_of_work_factory
        self._provider = provider
        self._worker_id = worker_id
        self._permissions = permissions
        self._max_parallelism = max_parallelism
        self._lease_seconds = lease_seconds
        self._max_attempts = max_attempts
        self._backoff_seconds = backoff_seconds
        self._max_backoff_seconds = max_backoff_seconds
        self._materialization_limit = materialization_limit
        self._clock = clock or (lambda: datetime.now(UTC))
        self._monitoring = CounterpartyMonitoringService(unit_of_work_factory)

    def run_once(
        self,
        *,
        scheduled_at: datetime | None = None,
        batch_key: str | None = None,
    ) -> CounterpartyMonitoringRunSummary:
        scheduled = scheduled_at or self._clock()
        self._validate_time(scheduled)
        daily_key = batch_key or f"counterparty-monitor:{scheduled.astimezone(UTC).date().isoformat()}"

        with self._unit_of_work_factory() as uow:
            batch = uow.counterparty_monitoring_batches.start_or_resume_daily_batch(
                batch_key=daily_key,
                scheduled_at=scheduled.astimezone(UTC),
            )
            batch = uow.counterparty_monitoring_batches.materialize_due_items(
                batch.batch_id,
                scheduled_at=scheduled.astimezone(UTC),
                limit=self._materialization_limit,
            )
            claimed = uow.counterparty_monitoring_batches.claim_items(
                batch.batch_id,
                self._worker_id,
                lease_seconds=self._lease_seconds,
                now=self._clock().astimezone(UTC),
                limit=self._max_parallelism,
            )

        results = []
        if claimed:
            with ThreadPoolExecutor(
                max_workers=self._max_parallelism,
                thread_name_prefix="counterparty-monitor",
            ) as pool:
                futures = [pool.submit(self._process_item, item) for item in claimed]
                for future in futures:
                    results.append(future.result())

        with self._unit_of_work_factory() as uow:
            final = uow.counterparty_monitoring_batches.finalize_batch(
                batch.batch_id,
                now=self._clock().astimezone(UTC),
            )

        completed = sum(item.state is BatchItemState.COMPLETED for item in results)
        retryable = sum(item.state is BatchItemState.RETRYABLE for item in results)
        failed = sum(item.state is BatchItemState.FAILED for item in results)
        return CounterpartyMonitoringRunSummary(
            batch_id=final.batch_id,
            batch_status=final.status,
            claimed=len(claimed),
            completed=completed,
            retryable=retryable,
            failed=failed,
            collection_complete=final.collection_complete,
        )

    def run_until_quiescent(
        self,
        *,
        scheduled_at: datetime | None = None,
        batch_key: str | None = None,
        max_cycles: int = 100,
    ) -> CounterpartyMonitoringRunSummary:
        if max_cycles < 1 or max_cycles > 1000:
            raise ValueError("max_cycles must be between 1 and 1000")
        last = self.run_once(scheduled_at=scheduled_at, batch_key=batch_key)
        for _ in range(max_cycles - 1):
            if last.batch_status is BatchStatus.COMPLETED:
                return last
            if last.claimed == 0:
                return last
            last = self.run_once(scheduled_at=scheduled_at, batch_key=batch_key)
        return last

    def _process_item(
        self,
        item: CounterpartyMonitoringBatchItem,
    ) -> CounterpartyMonitoringBatchItem:
        now = self._clock().astimezone(UTC)
        try:
            with self._unit_of_work_factory() as uow:
                monitor = uow.monitoring.get_monitor(item.monitor_id)
            if monitor is None or monitor.status.value != "active":
                return self._fail(
                    item,
                    retryable=False,
                    error_code="MONITOR_NOT_ACTIVE",
                    now=now,
                )

            observation = self._observe_with_budget(monitor, now=now)
            self._monitoring.record_observation(
                monitor_id=monitor.monitor_id,
                actor_id=monitor.actor_id,
                permissions=self._permissions,
                observation=observation,
                correlation_id=self._correlation_id(item),
                now=now,
                idempotency_key=f"{item.batch_id}:{item.monitor_id}",
            )
            return self._complete(item, now=now)
        except CounterpartyMonitoringProviderError as exc:
            return self._fail(
                item,
                retryable=exc.retryable,
                error_code=exc.code,
                now=now,
            )
        except (TimeoutError, ConnectionError) as exc:
            return self._fail(
                item,
                retryable=True,
                error_code=exc.__class__.__name__.upper(),
                now=now,
            )
        except IntegrityViolation:
            return self._fail(
                item,
                retryable=False,
                error_code="INTEGRITY_REJECTED",
                now=now,
            )
        except Exception as exc:
            return self._fail(
                item,
                retryable=True,
                error_code=f"UNEXPECTED:{type(exc).__name__}",
                now=now,
            )

    def _observe_with_budget(
        self,
        monitor: CounterpartyMonitor,
        *,
        now: datetime,
    ) -> CounterpartyObservation:
        return self._provider.observe(monitor, now=now)

    def _complete(
        self,
        item: CounterpartyMonitoringBatchItem,
        *,
        now: datetime,
    ) -> CounterpartyMonitoringBatchItem:
        with self._unit_of_work_factory() as uow:
            return uow.counterparty_monitoring_batches.complete_item(
                item.batch_id,
                item.monitor_id,
                self._worker_id,
                now=now,
            )

    def _fail(
        self,
        item: CounterpartyMonitoringBatchItem,
        *,
        retryable: bool,
        error_code: str,
        now: datetime,
    ) -> CounterpartyMonitoringBatchItem:
        should_retry = retryable and item.attempt < self._max_attempts
        delay = min(
            self._max_backoff_seconds,
            self._backoff_seconds * (2 ** max(item.attempt - 1, 0)),
        )
        available_at = now + timedelta(seconds=delay if should_retry else 0)
        with self._unit_of_work_factory() as uow:
            result = uow.counterparty_monitoring_batches.fail_item(
                item.batch_id,
                item.monitor_id,
                self._worker_id,
                retryable=should_retry,
                error_code=error_code,
                available_at=available_at,
                now=now,
            )
            uow.counterparty_monitoring_batches.set_monitor_error(
                item.monitor_id,
                error_code=error_code,
                now=now,
                next_check_at=available_at,
            )
            uow.audits.append(
                self._audit_for(
                    monitor_id=item.monitor_id,
                    batch_id=item.batch_id,
                    actor_id=self._worker_id,
                    outcome=result.state.value,
                    error_code=error_code,
                    occurred_at=now,
                )
            )
        return result

    @staticmethod
    def _audit_for(
        *,
        monitor_id: str,
        batch_id: str,
        actor_id: str,
        outcome: str,
        error_code: str,
        occurred_at: datetime,
    ):
        from shema_platform.foundation.audit import AuditRecord

        return AuditRecord(
            audit_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"counterparty-monitor-worker:{batch_id}:{monitor_id}:{error_code}:{occurred_at.isoformat()}",
                )
            ),
            actor_id=actor_id,
            action="counterparty.monitor.worker",
            resource_type="counterparty_monitor",
            resource_id=monitor_id,
            outcome=outcome,
            occurred_at=occurred_at,
            metadata={"batch_id": batch_id, "error_code": error_code},
            correlation_id=CounterpartyMonitoringWorker._correlation_id_from(
                batch_id,
                monitor_id,
            ),
        )

    @staticmethod
    def _correlation_id(item: CounterpartyMonitoringBatchItem) -> str:
        return CounterpartyMonitoringWorker._correlation_id_from(
            item.batch_id,
            item.monitor_id,
        )

    @staticmethod
    def _correlation_id_from(batch_id: str, monitor_id: str) -> str:
        return f"counterparty-monitor:{batch_id}:{monitor_id}"

    @staticmethod
    def _validate_time(value: datetime) -> None:
        if value.tzinfo is None:
            raise ValueError("scheduled_at must be timezone-aware")

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from shema_platform.application.counterparty_monitoring_worker import (
    BatchItemState,
    BatchStatus,
    CounterpartyMonitoringBatch,
    CounterpartyMonitoringBatchItem,
    CounterpartyMonitoringBatchRepository,
)
from shema_platform.foundation.errors import IntegrityViolation
from shema_platform.platform.postgres import DBConnection


def _batch_from_row(row: tuple[object, ...]) -> CounterpartyMonitoringBatch:
    return CounterpartyMonitoringBatch(
        batch_id=str(row[0]),
        batch_key=str(row[1]),
        scheduled_at=row[2],
        status=BatchStatus(str(row[3])),
        next_cursor=str(row[4]) if row[4] else None,
        collection_complete=bool(row[5]),
        created_at=row[6],
        completed_at=row[7],
    )


def _item_from_row(row: tuple[object, ...]) -> CounterpartyMonitoringBatchItem:
    return CounterpartyMonitoringBatchItem(
        batch_id=str(row[0]),
        monitor_id=str(row[1]),
        state=BatchItemState(str(row[2])),
        attempt=int(row[3]),
        available_at=row[4],
        lease_worker_id=str(row[5]) if row[5] else None,
        lease_until=row[6],
        last_error_code=str(row[7]) if row[7] else None,
        last_error_at=row[8],
        completed_at=row[9],
    )


class PostgresCounterpartyMonitoringBatchRepository(
    CounterpartyMonitoringBatchRepository
):
    def __init__(self, connection: DBConnection) -> None:
        self._connection = connection

    def start_or_resume_daily_batch(
        self,
        *,
        batch_key: str,
        scheduled_at: datetime,
    ) -> CounterpartyMonitoringBatch:
        batch_id = str(uuid5(NAMESPACE_URL, f"counterparty-monitor-batch:{batch_key}"))
        self._connection.execute(
            """
            insert into counterparty_monitoring_batch (
                batch_id, batch_key, scheduled_at, status,
                next_cursor, collection_complete, created_at, completed_at
            )
            values (%s, %s, %s, 'collecting', null, false, %s, null)
            on conflict (batch_key) do nothing
            """,
            (batch_id, batch_key, scheduled_at, scheduled_at),
        )
        row = self._connection.execute(
            """
            select
                batch_id, batch_key, scheduled_at, status,
                next_cursor, collection_complete, created_at, completed_at
            from counterparty_monitoring_batch
            where batch_key = %s
            """,
            (batch_key,),
        ).fetchone()
        if row is None:
            raise IntegrityViolation("counterparty monitoring batch disappeared")
        return _batch_from_row(row)

    def materialize_due_items(
        self,
        batch_id: str,
        *,
        scheduled_at: datetime,
        limit: int,
    ) -> CounterpartyMonitoringBatch:
        batch = self._get_for_update(batch_id)
        if batch.collection_complete:
            return batch
        lock_state = self._connection.execute(
            """
            select l.pid, l.mode, l.granted, l.page, l.tuple, a.state,
                   left(a.query, 160)
            from pg_locks l
            join pg_class c on c.oid = l.relation
            join pg_namespace n on n.oid = c.relnamespace
            left join pg_stat_activity a on a.pid = l.pid
            where n.nspname = current_schema()
              and c.relname = 'counterparty_monitoring_batch_item'
            order by l.pid, l.mode
            """,
        ).fetchall()
        print("CLAIM LOCK STATE DEBUG", lock_state)
        rows = self._connection.execute(
            """
            select monitor_id
            from counterparty_monitor
            where status = 'active'
              and next_check_at <= %s
              and (%s::text is null or monitor_id > %s)
            order by monitor_id
            limit %s
            """,
            (scheduled_at, batch.next_cursor, batch.next_cursor, limit),
        ).fetchall()
        last_cursor = batch.next_cursor
        for row in rows:
            monitor_id = str(row[0])
            last_cursor = monitor_id
            self._connection.execute(
                """
                insert into counterparty_monitoring_batch_item (
                    batch_id, monitor_id, state, attempt, available_at
                )
                values (%s, %s, 'pending', 0, %s)
                on conflict (batch_id, monitor_id) do nothing
                """,
                (batch_id, monitor_id, scheduled_at),
            )

        collection_complete = len(rows) < limit
        status = (
            BatchStatus.RUNNING.value
            if rows or batch.collection_complete or self._has_items(batch_id)
            else BatchStatus.COLLECTING.value
        )
        updated = self._connection.execute(
            """
            update counterparty_monitoring_batch
            set next_cursor = %s,
                collection_complete = %s,
                status = %s
            where batch_id = %s
            returning
                batch_id, batch_key, scheduled_at, status,
                next_cursor, collection_complete, created_at, completed_at
            """,
            (last_cursor, collection_complete, status, batch_id),
        ).fetchone()
        if updated is None:
            raise IntegrityViolation("counterparty monitoring batch update rejected")
        return _batch_from_row(updated)

    def claim_items(
        self,
        batch_id: str,
        worker_id: str,
        *,
        lease_seconds: int,
        now: datetime,
        limit: int,
    ) -> tuple[CounterpartyMonitoringBatchItem, ...]:
        claim_probe = self._connection.execute(
            "select batch_id, monitor_id, state, attempt, available_at, lease_worker_id, lease_until "
            "from counterparty_monitoring_batch_item "
            "where batch_id = %s and available_at <= %s and "
            "(state in ('pending', 'retryable') or (state = 'running' and lease_until < %s)) "
            "order by monitor_id",
            (batch_id, now, now),
        ).fetchall()
        print("CLAIM INTERNAL PLAIN DEBUG", claim_probe, "batch", batch_id, "limit", limit)
        rows = self._connection.execute(
            """
            select
                batch_id, monitor_id, state, attempt, available_at,
                lease_worker_id, lease_until, last_error_code,
                last_error_at, completed_at
            from counterparty_monitoring_batch_item
            where batch_id = %s
              and available_at <= %s
              and (
                    state in ('pending', 'retryable')
                    or (state = 'running' and lease_until < %s)
              )
            order by monitor_id
            for update skip locked
            limit %s
            """,
            (batch_id, now, now, limit),
        ).fetchall()
        result: list[CounterpartyMonitoringBatchItem] = []
        lease_until = now + timedelta(seconds=lease_seconds)
        for row in rows:
            monitor_id = str(row[1])
            updated = self._connection.execute(
                """
                update counterparty_monitoring_batch_item
                set state = 'running',
                    attempt = attempt + 1,
                    lease_worker_id = %s,
                    lease_until = %s,
                    last_error_code = null,
                    last_error_at = null
                where batch_id = %s
                  and monitor_id = %s
                  and (
                        state in ('pending', 'retryable')
                        or (state = 'running' and lease_until < %s)
                  )
                returning
                    batch_id, monitor_id, state, attempt, available_at,
                    lease_worker_id, lease_until, last_error_code,
                    last_error_at, completed_at
                """,
                (worker_id, lease_until, batch_id, monitor_id, now),
            ).fetchone()
            if updated is not None:
                result.append(_item_from_row(updated))
        return tuple(result)

    def complete_item(
        self,
        batch_id: str,
        monitor_id: str,
        worker_id: str,
        *,
        now: datetime,
    ) -> CounterpartyMonitoringBatchItem:
        row = self._connection.execute(
            """
            update counterparty_monitoring_batch_item
            set state = 'completed',
                lease_worker_id = null,
                lease_until = null,
                completed_at = %s
            where batch_id = %s
              and monitor_id = %s
              and state = 'running'
              and lease_worker_id = %s
              and lease_until >= %s
            returning
                batch_id, monitor_id, state, attempt, available_at,
                lease_worker_id, lease_until, last_error_code,
                last_error_at, completed_at
            """,
            (now, batch_id, monitor_id, worker_id, now),
        ).fetchone()
        if row is None:
            raise IntegrityViolation(
                "stale or unauthorized counterparty monitoring completion"
            )
        return _item_from_row(row)

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
    ) -> CounterpartyMonitoringBatchItem:
        state = (
            BatchItemState.RETRYABLE.value
            if retryable
            else BatchItemState.FAILED.value
        )
        row = self._connection.execute(
            """
            update counterparty_monitoring_batch_item
            set state = %s,
                available_at = %s,
                lease_worker_id = null,
                lease_until = null,
                last_error_code = %s,
                last_error_at = %s,
                completed_at = case when %s = 'failed' then %s else completed_at end
            where batch_id = %s
              and monitor_id = %s
              and state = 'running'
              and lease_worker_id = %s
              and lease_until >= %s
            returning
                batch_id, monitor_id, state, attempt, available_at,
                lease_worker_id, lease_until, last_error_code,
                last_error_at, completed_at
            """,
            (
                state,
                available_at,
                error_code,
                now,
                state,
                now,
                batch_id,
                monitor_id,
                worker_id,
                now,
            ),
        ).fetchone()
        if row is None:
            raise IntegrityViolation(
                "stale or unauthorized counterparty monitoring failure transition"
            )
        return _item_from_row(row)

    def set_monitor_error(
        self,
        monitor_id: str,
        *,
        error_code: str,
        now: datetime,
        next_check_at: datetime,
    ) -> None:
        updated = self._connection.execute(
            """
            update counterparty_monitor
            set last_error_code = %s,
                last_error_at = %s,
                next_check_at = %s,
                updated_at = %s
            where monitor_id = %s
            returning monitor_id
            """,
            (error_code, now, next_check_at, now, monitor_id),
        ).fetchone()
        if updated is None:
            raise IntegrityViolation("counterparty monitor error update rejected")

    def finalize_batch(
        self,
        batch_id: str,
        *,
        now: datetime,
    ) -> CounterpartyMonitoringBatch:
        pending = self._connection.execute(
            """
            select count(*)
            from counterparty_monitoring_batch_item
            where batch_id = %s
              and state in ('pending', 'running', 'retryable')
            """,
            (batch_id,),
        ).fetchone()[0]
        batch = self._get_for_update(batch_id)
        status = (
            BatchStatus.COMPLETED.value
            if batch.collection_complete and int(pending) == 0
            else BatchStatus.RUNNING.value
        )
        completed_at = now if status == BatchStatus.COMPLETED.value else None
        row = self._connection.execute(
            """
            update counterparty_monitoring_batch
            set status = %s,
                completed_at = case
                    when %s = 'completed' then coalesce(completed_at, %s)
                    else null
                end
            where batch_id = %s
            returning
                batch_id, batch_key, scheduled_at, status,
                next_cursor, collection_complete, created_at, completed_at
            """,
            (status, status, completed_at, batch_id),
        ).fetchone()
        if row is None:
            raise IntegrityViolation("counterparty monitoring batch finalize rejected")
        return _batch_from_row(row)

    def get_batch(self, batch_id: str) -> CounterpartyMonitoringBatch | None:
        row = self._connection.execute(
            """
            select
                batch_id, batch_key, scheduled_at, status,
                next_cursor, collection_complete, created_at, completed_at
            from counterparty_monitoring_batch
            where batch_id = %s
            """,
            (batch_id,),
        ).fetchone()
        return None if row is None else _batch_from_row(row)

    def _get_for_update(self, batch_id: str) -> CounterpartyMonitoringBatch:
        row = self._connection.execute(
            """
            select
                batch_id, batch_key, scheduled_at, status,
                next_cursor, collection_complete, created_at, completed_at
            from counterparty_monitoring_batch
            where batch_id = %s
            for update
            """,
            (batch_id,),
        ).fetchone()
        if row is None:
            raise IntegrityViolation("counterparty monitoring batch not found")
        return _batch_from_row(row)

    def _has_items(self, batch_id: str) -> bool:
        row = self._connection.execute(
            """
            select 1
            from counterparty_monitoring_batch_item
            where batch_id = %s
            limit 1
            """,
            (batch_id,),
        ).fetchone()
        return row is not None

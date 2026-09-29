from __future__ import annotations

import json
from datetime import datetime

from shema_platform.application.counterparty_monitoring import (
    CounterpartyChangeEvent,
    CounterpartyFavorite,
    CounterpartyMonitor,
    CounterpartyMonitoringRepository,
    CounterpartySnapshot,
    MonitoringStatus,
)
from shema_platform.application.counterparty_check import CounterpartyIdentifierType
from shema_platform.foundation.errors import IdempotencyConflict, IntegrityViolation
from shema_platform.platform.postgres import DBConnection


def _monitor_from_row(row: tuple[object, ...]) -> CounterpartyMonitor:
    (
        monitor_id,
        actor_id,
        identifier_type,
        identifier,
        status,
        frequency_seconds,
        next_check_at,
        last_checked_at,
        last_snapshot_id,
        last_error_code,
        last_error_at,
        created_at,
        updated_at,
    ) = row
    return CounterpartyMonitor(
        monitor_id=str(monitor_id),
        actor_id=str(actor_id),
        identifier_type=CounterpartyIdentifierType(str(identifier_type)),
        identifier=str(identifier),
        status=MonitoringStatus(str(status)),
        frequency_seconds=int(frequency_seconds),
        next_check_at=next_check_at,
        last_checked_at=last_checked_at,
        last_snapshot_id=str(last_snapshot_id) if last_snapshot_id else None,
        last_error_code=str(last_error_code) if last_error_code else None,
        last_error_at=last_error_at,
        created_at=created_at,
        updated_at=updated_at,
    )


def _favorite_from_row(row: tuple[object, ...]) -> CounterpartyFavorite:
    return CounterpartyFavorite(
        favorite_id=str(row[0]),
        actor_id=str(row[1]),
        identifier_type=CounterpartyIdentifierType(str(row[2])),
        identifier=str(row[3]),
        created_at=row[4],
    )


def _snapshot_from_row(row: tuple[object, ...]) -> CounterpartySnapshot:
    return CounterpartySnapshot(
        snapshot_id=str(row[0]),
        monitor_id=str(row[1]),
        observed_at=row[2],
        source_ref=str(row[3]),
        source_version=str(row[4]),
        payload=dict(row[5]),
        payload_hash=str(row[6]),
    )


class PostgresCounterpartyMonitoringRepository(CounterpartyMonitoringRepository):
    def __init__(self, connection: DBConnection) -> None:
        self._connection = connection

    def add_monitor(self, monitor: CounterpartyMonitor) -> None:
        self._connection.execute(
            """
            insert into counterparty_monitor (
                monitor_id, actor_id, identifier_type, identifier, status,
                frequency_seconds, next_check_at, last_checked_at,
                last_snapshot_id, last_error_code, last_error_at,
                created_at, updated_at
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (actor_id, identifier_type, identifier) do nothing
            """,
            (
                monitor.monitor_id,
                monitor.actor_id,
                monitor.identifier_type.value,
                monitor.identifier,
                monitor.status.value,
                monitor.frequency_seconds,
                monitor.next_check_at,
                monitor.last_checked_at,
                monitor.last_snapshot_id,
                monitor.last_error_code,
                monitor.last_error_at,
                monitor.created_at,
                monitor.updated_at,
            ),
        )
        stored = self.get_monitor(monitor.monitor_id)
        if stored is None:
            existing = self._connection.execute(
                """
                select monitor_id
                from counterparty_monitor
                where actor_id = %s
                  and identifier_type = %s
                  and identifier = %s
                """,
                (monitor.actor_id, monitor.identifier_type.value, monitor.identifier),
            ).fetchone()
            if existing is None:
                raise IntegrityViolation("monitor disappeared after insert")
            raise IdempotencyConflict("counterparty monitor already exists")
        if stored != monitor:
            raise IdempotencyConflict("counterparty monitor already exists")

    def get_monitor(self, monitor_id: str) -> CounterpartyMonitor | None:
        row = self._connection.execute(
            """
            select
                monitor_id, actor_id, identifier_type, identifier, status,
                frequency_seconds, next_check_at, last_checked_at,
                last_snapshot_id, last_error_code, last_error_at,
                created_at, updated_at
            from counterparty_monitor
            where monitor_id = %s
            """,
            (monitor_id,),
        ).fetchone()
        return None if row is None else _monitor_from_row(row)

    def get_monitor_for_actor(
        self,
        monitor_id: str,
        actor_id: str,
    ) -> CounterpartyMonitor | None:
        row = self._connection.execute(
            """
            select
                monitor_id, actor_id, identifier_type, identifier, status,
                frequency_seconds, next_check_at, last_checked_at,
                last_snapshot_id, last_error_code, last_error_at,
                created_at, updated_at
            from counterparty_monitor
            where monitor_id = %s
              and actor_id = %s
            """,
            (monitor_id, actor_id),
        ).fetchone()
        return None if row is None else _monitor_from_row(row)

    def list_monitors(self, actor_id: str) -> tuple[CounterpartyMonitor, ...]:
        rows = self._connection.execute(
            """
            select
                monitor_id, actor_id, identifier_type, identifier, status,
                frequency_seconds, next_check_at, last_checked_at,
                last_snapshot_id, last_error_code, last_error_at,
                created_at, updated_at
            from counterparty_monitor
            where actor_id = %s
            order by created_at desc, monitor_id desc
            """,
            (actor_id,),
        ).fetchall()
        return tuple(_monitor_from_row(row) for row in rows)

    def add_favorite(self, favorite: CounterpartyFavorite) -> None:
        self._connection.execute(
            """
            insert into counterparty_favorite (
                favorite_id, actor_id, identifier_type, identifier, created_at
            )
            values (%s, %s, %s, %s, %s)
            on conflict (actor_id, identifier_type, identifier) do nothing
            """,
            (
                favorite.favorite_id,
                favorite.actor_id,
                favorite.identifier_type.value,
                favorite.identifier,
                favorite.created_at,
            ),
        )
        stored = self.get_favorite(favorite.favorite_id)
        if stored is None:
            raise IntegrityViolation("favorite disappeared after insert")
        if stored != favorite:
            raise IdempotencyConflict("counterparty favorite already exists")

    def get_favorite(self, favorite_id: str) -> CounterpartyFavorite | None:
        row = self._connection.execute(
            """
            select favorite_id, actor_id, identifier_type, identifier, created_at
            from counterparty_favorite
            where favorite_id = %s
            """,
            (favorite_id,),
        ).fetchone()
        return None if row is None else _favorite_from_row(row)

    def list_favorites(self, actor_id: str) -> tuple[CounterpartyFavorite, ...]:
        rows = self._connection.execute(
            """
            select favorite_id, actor_id, identifier_type, identifier, created_at
            from counterparty_favorite
            where actor_id = %s
            order by created_at desc, favorite_id desc
            """,
            (actor_id,),
        ).fetchall()
        return tuple(_favorite_from_row(row) for row in rows)

    def get_latest_snapshot(self, monitor_id: str) -> CounterpartySnapshot | None:
        row = self._connection.execute(
            """
            select
                snapshot_id, monitor_id, observed_at, source_ref,
                source_version, payload, payload_hash
            from counterparty_snapshot
            where monitor_id = %s
            order by observed_at desc, snapshot_id desc
            limit 1
            """,
            (monitor_id,),
        ).fetchone()
        return None if row is None else _snapshot_from_row(row)

    def add_snapshot(self, snapshot: CounterpartySnapshot) -> CounterpartySnapshot:
        self._connection.execute(
            """
            insert into counterparty_snapshot (
                snapshot_id, monitor_id, observed_at, source_ref,
                source_version, payload, payload_hash, created_at
            )
            values (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
            on conflict (monitor_id, observed_at, payload_hash) do nothing
            """,
            (
                snapshot.snapshot_id,
                snapshot.monitor_id,
                snapshot.observed_at,
                snapshot.source_ref,
                snapshot.source_version,
                json.dumps(snapshot.payload, ensure_ascii=False, sort_keys=True),
                snapshot.payload_hash,
                snapshot.observed_at,
            ),
        )
        row = self._connection.execute(
            """
            select
                snapshot_id, monitor_id, observed_at, source_ref,
                source_version, payload, payload_hash
            from counterparty_snapshot
            where monitor_id = %s
              and observed_at = %s
              and payload_hash = %s
            """,
            (snapshot.monitor_id, snapshot.observed_at, snapshot.payload_hash),
        ).fetchone()
        if row is None:
            raise IntegrityViolation("counterparty snapshot disappeared after insert")
        return _snapshot_from_row(row)

    def set_last_snapshot(
        self,
        monitor_id: str,
        *,
        snapshot_id: str,
        checked_at: datetime,
        next_check_at: datetime,
    ) -> None:
        updated = self._connection.execute(
            """
            update counterparty_monitor
            set last_snapshot_id = %s,
                last_checked_at = %s,
                next_check_at = %s,
                last_error_code = null,
                last_error_at = null,
                updated_at = %s
            where monitor_id = %s
            returning monitor_id
            """,
            (
                snapshot_id,
                checked_at,
                next_check_at,
                checked_at,
                monitor_id,
            ),
        ).fetchone()
        if updated is None:
            raise IntegrityViolation("counterparty monitor update rejected")

    def add_change_event(self, event: CounterpartyChangeEvent) -> None:
        self._connection.execute(
            """
            insert into counterparty_change_event (
                change_id,
                monitor_id,
                before_snapshot_id,
                after_snapshot_id,
                changed_parameters,
                severity,
                source_ref,
                freshness,
                correlation_id,
                notification_id,
                detected_at
            )
            values (
                %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s
            )
            on conflict (monitor_id, before_snapshot_id, after_snapshot_id)
            do nothing
            """,
            (
                event.change_id,
                event.monitor_id,
                event.before_snapshot_id,
                event.after_snapshot_id,
                json.dumps(event.changed_parameters, ensure_ascii=False, sort_keys=True),
                event.severity.value,
                event.source_ref,
                event.freshness,
                event.correlation_id,
                event.notification_id,
                event.detected_at,
            ),
        )

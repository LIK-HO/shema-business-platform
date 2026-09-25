from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from shema_platform.platform.postgres import DBConnection


@dataclass(frozen=True, slots=True)
class QuarantineRecordView:
    quarantine_id: str
    object_type: str
    object_ref: str
    reason_code: str
    payload: dict[str, object]
    created_at: datetime
    resolved_at: datetime | None
    resolution: str | None


class QuarantineReader(Protocol):
    """Read-only platform contract for uncertainty inspection."""

    def get_open(
        self,
        *,
        object_type: str,
        object_ref: str,
        reason_code: str | None = None,
    ) -> tuple[QuarantineRecordView, ...]: ...

    def list_open(self, *, limit: int = 100) -> tuple[QuarantineRecordView, ...]: ...


class PostgresQuarantineReader:
    """Read-only access to existing quarantine records."""

    def __init__(self, connection: DBConnection) -> None:
        self._connection = connection

    def get_open(
        self,
        *,
        object_type: str,
        object_ref: str,
        reason_code: str | None = None,
    ) -> tuple[QuarantineRecordView, ...]:
        if not object_type.strip() or not object_ref.strip():
            raise ValueError("object_type and object_ref are required")
        if reason_code is not None and not reason_code.strip():
            raise ValueError("reason_code cannot be blank")

        if reason_code is None:
            cursor = self._connection.execute(
                """
                select
                    quarantine_id,
                    object_type,
                    object_ref,
                    reason_code,
                    payload,
                    created_at,
                    resolved_at,
                    resolution
                from quarantine_record
                where object_type = %s
                  and object_ref = %s
                  and resolved_at is null
                order by created_at desc
                """,
                (object_type, object_ref),
            )
        else:
            cursor = self._connection.execute(
                """
                select
                    quarantine_id,
                    object_type,
                    object_ref,
                    reason_code,
                    payload,
                    created_at,
                    resolved_at,
                    resolution
                from quarantine_record
                where object_type = %s
                  and object_ref = %s
                  and reason_code = %s
                  and resolved_at is null
                order by created_at desc
                """,
                (object_type, object_ref, reason_code),
            )

        return tuple(self._to_view(row) for row in cursor.fetchall())

    def list_open(self, *, limit: int = 100) -> tuple[QuarantineRecordView, ...]:
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")

        cursor = self._connection.execute(
            """
            select
                quarantine_id,
                object_type,
                object_ref,
                reason_code,
                payload,
                created_at,
                resolved_at,
                resolution
            from quarantine_record
            where resolved_at is null
            order by created_at asc
            limit %s
            """,
            (limit,),
        )
        return tuple(self._to_view(row) for row in cursor.fetchall())

    @staticmethod
    def _to_view(row: tuple[object, ...]) -> QuarantineRecordView:
        (
            quarantine_id,
            object_type,
            object_ref,
            reason_code,
            payload,
            created_at,
            resolved_at,
            resolution,
        ) = row
        return QuarantineRecordView(
            quarantine_id=str(quarantine_id),
            object_type=str(object_type),
            object_ref=str(object_ref),
            reason_code=str(reason_code),
            payload=dict(payload),
            created_at=created_at,
            resolved_at=resolved_at,
            resolution=(
                str(resolution) if resolution is not None else None
            ),
        )

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True, slots=True)
class AuditRecord:
    audit_id: str
    actor_id: str
    action: str
    resource_type: str
    resource_id: str | None
    outcome: str
    occurred_at: datetime
    metadata: dict[str, Any]


class AuditLog:
    """Append-only application contract; durable storage belongs to infrastructure."""

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    def append(self, *, audit_id: str, actor_id: str, action: str,
               resource_type: str, resource_id: str | None, outcome: str,
               metadata: dict[str, Any] | None = None) -> AuditRecord:
        record = AuditRecord(
            audit_id=audit_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            occurred_at=datetime.now(timezone.utc),
            metadata=dict(metadata or {}),
        )
        self._records.append(record)
        return record

    def all(self) -> tuple[AuditRecord, ...]:
        return tuple(self._records)

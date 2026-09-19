from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
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
    metadata: Mapping[str, Any]
    correlation_id: str | None = None
    configuration_version: str | None = None

    def __post_init__(self) -> None:
        if not self.audit_id.strip() or not self.actor_id.strip():
            raise ValueError("audit_id and actor_id are required")
        if not self.action.strip() or not self.resource_type.strip():
            raise ValueError("action and resource_type are required")
        if not self.outcome.strip():
            raise ValueError("outcome is required")

        object.__setattr__(
            self,
            "metadata",
            MappingProxyType(dict(self.metadata)),
        )


class AuditLog:
    """Append-only application contract; durable storage belongs to infrastructure."""

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    def append(
        self,
        *,
        audit_id: str,
        actor_id: str,
        action: str,
        resource_type: str,
        resource_id: str | None,
        outcome: str,
        metadata: Mapping[str, Any] | None = None,
        correlation_id: str | None = None,
        configuration_version: str | None = None,
    ) -> AuditRecord:
        record = AuditRecord(
            audit_id=audit_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            occurred_at=datetime.now(UTC),
            metadata=metadata or {},
            correlation_id=correlation_id,
            configuration_version=configuration_version,
        )
        self._records.append(record)
        return record

    def all(self) -> tuple[AuditRecord, ...]:
        return tuple(self._records)

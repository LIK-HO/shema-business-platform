from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class CorrelationContext:
    """Stable identifiers that connect request, command, job and business objects."""

    correlation_id: UUID
    request_id: UUID | None = None
    command_id: str | None = None
    job_id: str | None = None
    actor_id: str | None = None
    provider_id: str | None = None
    entity_id: str | None = None

    @classmethod
    def new(cls, *, request_id: UUID | None = None) -> CorrelationContext:
        return cls(correlation_id=uuid4(), request_id=request_id)

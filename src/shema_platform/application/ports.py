from __future__ import annotations

from typing import Protocol

from shema_platform.domain.identity import Identity
from shema_platform.domain.search import SearchHit
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.evidence import Evidence
from shema_platform.foundation.idempotency import IdempotencyRecord
from shema_platform.foundation.outbox import OutboxEvent


class IdentityRepository(Protocol):
    """Persistence port for canonical identities."""

    def find_by_tax_id(self, tax_id: str) -> Identity | None: ...

    def add(self, identity: Identity) -> None: ...


class SearchCandidateRepository(Protocol):
    """Persistence port for source-side discovery observations."""

    def add(self, candidate: SearchHit) -> None: ...


class QuarantineRepository(Protocol):
    """Persistence port for uncertain/conflicting records."""

    def add(
        self,
        *,
        object_type: str,
        object_ref: str,
        reason_code: str,
        payload: dict[str, object],
    ) -> None: ...


class EvidenceRepository(Protocol):
    """Persistence port for traceable evidence."""

    def add(self, evidence: Evidence) -> None: ...


class AuditRepository(Protocol):
    """Append-only persistence port for application audit records."""

    def append(self, record: AuditRecord) -> None: ...


class IdempotencyRepository(Protocol):
    """Persistence port for critical command idempotency."""

    def reserve(self, key: str, request_hash: str, result_ref: str) -> IdempotencyRecord: ...

    def get(self, key: str) -> IdempotencyRecord | None: ...


class OutboxRepository(Protocol):
    """Persistence port for transactional outbox events."""

    def append(self, event: OutboxEvent) -> OutboxEvent: ...

    def pending(self) -> tuple[OutboxEvent, ...]: ...

    def mark_published(self, event_id: str) -> OutboxEvent: ...

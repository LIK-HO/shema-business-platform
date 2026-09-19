from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Protocol, Self

from shema_platform.domain.commercial_action import CommercialAction
from shema_platform.domain.economics import EconomicEntry
from shema_platform.domain.identity import Identity
from shema_platform.domain.order import Order
from shema_platform.domain.search import SearchHit
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.evidence import Evidence
from shema_platform.foundation.idempotency import IdempotencyRecord
from shema_platform.foundation.jobs import JobRecord
from shema_platform.foundation.outbox import OutboxEvent

if TYPE_CHECKING:
    from shema_platform.application.ai import AIRun


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


class JobRepository(Protocol):
    """Persistence port for durable worker execution state."""

    def enqueue(self, record: JobRecord) -> JobRecord: ...

    def get(self, job_id: str) -> JobRecord | None: ...

    def claim_next(
        self,
        worker_id: str,
        *,
        lease_seconds: int,
        now: datetime,
    ) -> JobRecord | None: ...

    def complete(self, job_id: str, worker_id: str, *, now: datetime) -> JobRecord: ...

    def fail(
        self,
        job_id: str,
        worker_id: str,
        *,
        retryable: bool,
        error: str,
        available_at: datetime,
        now: datetime,
    ) -> JobRecord: ...


class CommercialActionRepository(Protocol):
    """Persistence port for commercial action state transitions."""

    def add(self, action: CommercialAction) -> None: ...

    def get(self, action_id: str) -> CommercialAction | None: ...

    def save(self, action: CommercialAction) -> None: ...


class OrderRepository(Protocol):
    """Persistence port for order headers and lines."""

    def add(self, order: Order) -> None: ...

    def get(self, order_id: str) -> Order | None: ...

    def save(self, order: Order) -> None: ...


class EconomicEntryRepository(Protocol):
    """Append-only persistence port for traceable economic entries."""

    def add(self, entry: EconomicEntry) -> None: ...

    def list_for_entity(self, entity_ref: str) -> tuple[EconomicEntry, ...]: ...


class AIRunRepository(Protocol):
    """Persistence port for traceable AI execution results."""

    def add(self, run: AIRun) -> None: ...

    def get(self, run_id: str) -> AIRun | None: ...


class UnitOfWork(Protocol):
    """Application transaction boundary shared by all durable workflows."""

    identities: IdentityRepository
    evidence: EvidenceRepository
    audits: AuditRepository
    idempotency: IdempotencyRepository
    outbox: OutboxRepository
    commercial_actions: CommercialActionRepository
    orders: OrderRepository
    economics: EconomicEntryRepository
    ai_runs: AIRunRepository

    def __enter__(self) -> Self: ...

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> bool: ...

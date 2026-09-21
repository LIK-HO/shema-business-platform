from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Protocol, Self

from shema_platform.domain.commercial_action import CommercialAction
from shema_platform.domain.economics import EconomicEntry
from shema_platform.domain.identity import Identity
from shema_platform.domain.money import Money
from shema_platform.domain.order import Order
from shema_platform.domain.payment import (
    PaymentAttempt,
    PaymentAttemptStatus,
    PaymentIntent,
    ProviderEvent,
)
from shema_platform.domain.payment_adjustment import PaymentAdjustment
from shema_platform.domain.search import SearchHit
from shema_platform.domain.settlement import (
    ReconciliationItem,
    SettlementLine,
    SettlementRecord,
)
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.evidence import Evidence
from shema_platform.foundation.idempotency import IdempotencyRecord
from shema_platform.foundation.jobs import JobRecord
from shema_platform.foundation.outbox import OutboxDelivery, OutboxEvent

if TYPE_CHECKING:
    from shema_platform.application.ai import AIRun


class IdentityRepository(Protocol):
    """Persistence port for canonical identities."""

    def find_by_tax_id(self, tax_id: str) -> Identity | None: ...

    def get(self, identity_id: str) -> Identity | None: ...

    def list_all(self) -> tuple[Identity, ...]: ...

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
    """Persistence port for critical command idempotency and completion."""

    def reserve(self, key: str, request_hash: str, result_ref: str) -> IdempotencyRecord: ...

    def complete(self, key: str, request_hash: str, result_ref: str) -> IdempotencyRecord: ...

    def get(self, key: str) -> IdempotencyRecord | None: ...


class OutboxRepository(Protocol):
    """Persistence port for transactional outbox events and delivery leases."""

    def append(self, event: OutboxEvent) -> OutboxEvent: ...

    def pending(self) -> tuple[OutboxEvent, ...]: ...

    def claim_pending(
        self,
        worker_id: str,
        *,
        lease_seconds: int,
        now: datetime,
        limit: int,
    ) -> tuple[OutboxDelivery, ...]: ...

    def mark_published(
        self,
        event_id: str,
        worker_id: str,
        *,
        now: datetime,
    ) -> OutboxEvent: ...


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

    def renew(
        self,
        job_id: str,
        worker_id: str,
        *,
        lease_seconds: int,
        now: datetime,
    ) -> JobRecord: ...

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

    def claim_for_send(
        self,
        action_id: str,
        worker_id: str,
        *,
        lease_until: datetime,
        now: datetime,
    ) -> CommercialAction: ...

    def complete_send(
        self,
        action_id: str,
        worker_id: str,
        *,
        now: datetime,
    ) -> CommercialAction: ...

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


class PaymentIntentRepository(Protocol):
    """Persistence port for platform payment intent state."""

    def add(self, payment: PaymentIntent) -> None: ...

    def get(self, payment_id: str) -> PaymentIntent | None: ...

    def save(self, payment: PaymentIntent) -> None: ...


class PaymentAttemptRepository(Protocol):
    """Lease-guarded persistence port for provider payment attempts."""

    def add(self, attempt: PaymentAttempt) -> None: ...

    def get(self, attempt_id: str) -> PaymentAttempt | None: ...

    def find_by_provider_ref(self, provider_ref: str) -> PaymentAttempt | None: ...

    def claim_for_send(
        self,
        attempt_id: str,
        worker_id: str,
        *,
        lease_until: datetime,
        now: datetime,
    ) -> PaymentAttempt: ...

    def complete(
        self,
        attempt_id: str,
        worker_id: str,
        *,
        status: PaymentAttemptStatus,
        provider_ref: str | None,
        now: datetime,
    ) -> PaymentAttempt: ...

    def apply_provider_result(
        self,
        attempt_id: str,
        *,
        status: PaymentAttemptStatus,
        provider_ref: str | None,
    ) -> PaymentAttempt: ...


class PaymentAdjustmentRepository(Protocol):
    """Append-only provider adjustment facts."""

    def add(self, adjustment: PaymentAdjustment) -> None: ...

    def get_by_provider_event(
        self,
        provider_event_id: str,
    ) -> PaymentAdjustment | None: ...

    def find_by_provider_ref(
        self,
        provider_ref: str,
    ) -> PaymentAdjustment | None: ...

    def total_for_payment(self, payment_id: str) -> Money: ...


class ProviderEventRepository(Protocol):
    """Idempotent persistence port for verified provider events."""

    def add(self, event: ProviderEvent) -> None: ...

    def get(self, event_id: str) -> ProviderEvent | None: ...

    def mark_processed(
        self,
        event_id: str,
        *,
        status: ProviderEventStatus,
        processed_at: datetime,
    ) -> ProviderEvent: ...


class SettlementRepository(Protocol):
    """Persistence port for provider settlement facts."""

    def add(self, settlement: SettlementRecord) -> None: ...

    def get(self, settlement_id: str) -> SettlementRecord | None: ...

    def save(self, settlement: SettlementRecord) -> None: ...

    def add_line(self, line: SettlementLine) -> None: ...

    def list_lines(self, settlement_id: str) -> tuple[SettlementLine, ...]: ...


class ReconciliationRepository(Protocol):
    """Append-only-ish review state for settlement discrepancies."""

    def add(self, item: ReconciliationItem) -> None: ...

    def get(self, reconciliation_id: str) -> ReconciliationItem | None: ...

    def resolve(self, item: ReconciliationItem) -> ReconciliationItem: ...

    def list_open_for_settlement(
        self,
        settlement_id: str,
    ) -> tuple[ReconciliationItem, ...]: ...


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
    jobs: JobRepository
    quarantine: QuarantineRepository
    commercial_actions: CommercialActionRepository
    orders: OrderRepository
    economics: EconomicEntryRepository
    payments: PaymentIntentRepository
    payment_attempts: PaymentAttemptRepository
    provider_events: ProviderEventRepository
    payment_adjustments: PaymentAdjustmentRepository
    settlements: SettlementRepository
    reconciliations: ReconciliationRepository
    ai_runs: AIRunRepository

    def __enter__(self) -> Self: ...

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> bool: ...

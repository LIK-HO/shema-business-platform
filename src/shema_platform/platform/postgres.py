from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol, Self

if TYPE_CHECKING:
    from shema_platform.application.ports import (
        AIRunRepository,
        AuditRepository,
        CommercialActionRepository,
        EconomicEntryRepository,
        EvidenceRepository,
        IdentityRepository,
        IdempotencyRepository,
        OrderRepository,
        OutboxRepository,
    )


class DBCursor(Protocol):
    def fetchone(self) -> tuple[object, ...] | None: ...

    def fetchall(self) -> list[tuple[object, ...]]: ...


class DBConnection(Protocol):
    """Minimal DB-API contract required by the platform."""

    def execute(
        self,
        statement: str,
        parameters: tuple[object, ...] = (),
    ) -> DBCursor: ...

    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def close(self) -> None: ...


class PostgresUnitOfWork:
    """Database transaction boundary with explicit commit/rollback semantics.

    A real PostgreSQL connection factory is injected at composition time. The
    application and domain layers remain unaware of the driver.
    """

    def __init__(self, connection_factory: Callable[[], DBConnection]) -> None:
        self._connection_factory = connection_factory
        self._connection: DBConnection | None = None
        self.identities: IdentityRepository | None = None
        self.evidence: EvidenceRepository | None = None
        self.audits: AuditRepository | None = None
        self.idempotency: IdempotencyRepository | None = None
        self.outbox: OutboxRepository | None = None
        self.commercial_actions: CommercialActionRepository | None = None
        self.orders: OrderRepository | None = None
        self.economics: EconomicEntryRepository | None = None
        self.ai_runs: AIRunRepository | None = None

    @property
    def connection(self) -> DBConnection:
        if self._connection is None:
            raise RuntimeError("unit of work is not active")
        return self._connection

    def __enter__(self) -> Self:
        if self._connection is not None:
            raise RuntimeError("unit of work is already active")
        self._connection = self._connection_factory()

        from shema_platform.platform.postgres_repositories import (
            PostgresAIRunRepository,
            PostgresAuditRepository,
            PostgresCommercialActionRepository,
            PostgresEconomicEntryRepository,
            PostgresEvidenceRepository,
            PostgresIdentityRepository,
            PostgresIdempotencyRepository,
            PostgresOrderRepository,
            PostgresOutboxRepository,
        )

        connection = self.connection
        self.identities = PostgresIdentityRepository(connection)
        self.evidence = PostgresEvidenceRepository(connection)
        self.audits = PostgresAuditRepository(connection)
        self.idempotency = PostgresIdempotencyRepository(connection)
        self.outbox = PostgresOutboxRepository(connection)
        self.commercial_actions = PostgresCommercialActionRepository(connection)
        self.orders = PostgresOrderRepository(connection)
        self.economics = PostgresEconomicEntryRepository(connection)
        self.ai_runs = PostgresAIRunRepository(connection)
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        connection = self._connection
        self._connection = None
        self.identities = None
        self.evidence = None
        self.audits = None
        self.idempotency = None
        self.outbox = None
        self.commercial_actions = None
        self.orders = None
        self.economics = None
        self.ai_runs = None
        if connection is None:
            return False

        try:
            if exc_type is None:
                connection.commit()
            else:
                connection.rollback()
        finally:
            connection.close()

        return False

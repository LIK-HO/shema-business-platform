from __future__ import annotations

from typing import Protocol, Self


class DBConnection(Protocol):
    """Minimal connection contract required by the platform UoW."""

    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def close(self) -> None: ...


class PostgresUnitOfWork:
    """Database transaction boundary with explicit commit/rollback semantics.

    A real PostgreSQL connection factory is injected at composition time. The
    application and domain layers remain unaware of the driver.
    """

    def __init__(self, connection_factory: callable[[], DBConnection]) -> None:
        self._connection_factory = connection_factory
        self._connection: DBConnection | None = None

    @property
    def connection(self) -> DBConnection:
        if self._connection is None:
            raise RuntimeError("unit of work is not active")
        return self._connection

    def __enter__(self) -> Self:
        if self._connection is not None:
            raise RuntimeError("unit of work is already active")
        self._connection = self._connection_factory()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        connection = self._connection
        self._connection = None
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

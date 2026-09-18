from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Protocol, Self


class Transaction(AbstractContextManager["Transaction"], Protocol):
    """Database-neutral transaction contract."""

    def commit(self) -> None: ...
    def rollback(self) -> None: ...

    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type, exc_value, traceback) -> bool | None: ...


class UnitOfWork(Protocol):
    """Application transaction boundary.

    Domain logic knows only this contract. The PostgreSQL implementation owns
    connection and transaction details and is replaceable without changing use cases.
    """

    transaction: Transaction

    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type, exc_value, traceback) -> bool | None: ...

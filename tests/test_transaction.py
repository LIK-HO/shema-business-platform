import pytest

from shema_platform.platform.postgres import DBConnection, PostgresUnitOfWork


class FakeConnection(DBConnection):
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def test_unit_of_work_commits_and_closes() -> None:
    connection = FakeConnection()
    with PostgresUnitOfWork(lambda: connection) as uow:
        assert uow.connection is connection

    assert connection.committed
    assert not connection.rolled_back
    assert connection.closed


def test_unit_of_work_rolls_back_and_closes_on_error() -> None:
    connection = FakeConnection()

    with pytest.raises(RuntimeError):
        with PostgresUnitOfWork(lambda: connection):
            raise RuntimeError("transaction failure")

    assert not connection.committed
    assert connection.rolled_back
    assert connection.closed


def test_unit_of_work_does_not_swallow_errors() -> None:
    connection = FakeConnection()

    with pytest.raises(ValueError, match="domain failure"):
        with PostgresUnitOfWork(lambda: connection):
            raise ValueError("domain failure")

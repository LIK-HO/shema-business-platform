from dataclasses import dataclass

from shema_platform.domain.identity import Identity, IdentityState
from shema_platform.platform.postgres import DBConnection
from shema_platform.platform.postgres_repositories import (
    PostgresIdentityRepository,
    PostgresQuarantineRepository,
)


@dataclass
class FakeCursor:
    row: tuple[object, ...] | None = None

    def fetchone(self) -> tuple[object, ...] | None:
        return self.row


class FakeConnection(DBConnection):
    def __init__(self, row: tuple[object, ...] | None = None) -> None:
        self.row = row
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(
        self,
        statement: str,
        parameters: tuple[object, ...] = (),
    ) -> FakeCursor:
        self.calls.append((statement, parameters))
        return FakeCursor(self.row)

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass


def test_identity_repository_maps_row_without_business_decisions() -> None:
    connection = FakeConnection(
        ("identity-1", "ООО Альфа", "verified", "7700000000", "1027700000000")
    )
    repository = PostgresIdentityRepository(connection)

    identity = repository.find_by_tax_id(" 7700000000 ")

    assert identity == Identity(
        "identity-1",
        "ООО Альфа",
        IdentityState.VERIFIED,
        tax_id="7700000000",
        registration_id="1027700000000",
    )
    assert connection.calls[0][1] == ("7700000000",)


def test_identity_repository_uses_parameterized_insert() -> None:
    connection = FakeConnection()
    repository = PostgresIdentityRepository(connection)
    identity = Identity(
        "identity-1",
        "ООО Альфа",
        IdentityState.IDENTIFIED,
        tax_id="7700000000",
    )

    repository.add(identity)

    assert connection.calls
    statement, parameters = connection.calls[0]
    assert "%s" in statement
    assert "7700000000" in parameters


def test_quarantine_repository_serializes_payload_as_json() -> None:
    connection = FakeConnection()
    repository = PostgresQuarantineRepository(connection)

    repository.add(
        object_type="search_candidate",
        object_ref="candidate-1",
        reason_code="missing_tax_id",
        payload={"name": "ООО Альфа"},
    )

    statement, parameters = connection.calls[0]
    assert "%s::jsonb" in statement
    assert parameters[0:3] == (
        "search_candidate",
        "candidate-1",
        "missing_tax_id",
    )
    assert '"name": "ООО Альфа"' in str(parameters[3])

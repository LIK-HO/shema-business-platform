from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from shema_platform.domain.commercial_action import CommercialAction
from shema_platform.domain.identity import Identity, IdentityState
from shema_platform.domain.money import Money
from shema_platform.domain.order import Order, OrderLine
from shema_platform.domain.repeat_order import (
    RepeatCadence,
    RepeatCadenceUnit,
    RepeatOrderContext,
    RepeatOrderPlan,
)
from shema_platform.foundation.errors import IntegrityViolation
from shema_platform.platform.postgres import DBConnection
from shema_platform.platform.postgres_repositories import (
    PostgresCommercialActionRepository,
    PostgresIdentityRepository,
    PostgresOrderRepository,
    PostgresQuarantineRepository,
    PostgresRepeatOrderRepository,
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
    assert parameters[1:4] == (
        "search_candidate",
        "candidate-1",
        "missing_tax_id",
    )
    assert '"name": "ООО Альфа"' in str(parameters[4])


def test_commercial_action_owner_cannot_be_reassigned() -> None:
    connection = FakeConnection(
        (
            "action-1",
            "identity-1",
            "chat:1",
            "max",
            ["evidence-1"],
            "ready",
            "operator-1",
            0,
            None,
            None,
        )
    )
    repository = PostgresCommercialActionRepository(connection)
    action = CommercialAction(
        action_id="action-1",
        identity_id="identity-1",
        contact_ref="chat:1",
        channel="max",
        evidence_refs=("evidence-1",),
        owner_actor_id="operator-2",
    )

    with pytest.raises(IntegrityViolation, match="owner scope is immutable"):
        repository.save(action)


def test_order_owner_cannot_be_reassigned() -> None:
    connection = FakeConnection(
        (
            "order-1",
            "identity-1",
            "action-1",
            "draft",
            "operator-1",
        )
    )
    repository = PostgresOrderRepository(connection)
    order = Order(
        order_id="order-1",
        identity_id="identity-1",
        source_action_id="action-1",
        lines=(
            OrderLine(
                "line-1",
                "Погрузка",
                Decimal("1"),
                Money(1500, "RUB"),
            ),
        ),
        owner_actor_id="operator-2",
    )

    with pytest.raises(IntegrityViolation, match="owner scope is immutable"):
        repository.save(order)


def test_repeat_order_plan_owner_cannot_be_reassigned() -> None:
    connection = FakeConnection(
        (
            "plan-1",
            "order-1",
            "operator-1",
            "identity-1",
            "active",
            "week",
            1,
            datetime(2026, 10, 1, 9, tzinfo=UTC),
            "Погрузка",
            Decimal("1"),
            None,
            None,
            0,
            1,
        )
    )
    repository = PostgresRepeatOrderRepository(connection)
    plan = RepeatOrderPlan(
        plan_id="plan-1",
        source_order_id="order-1",
        owner_actor_id="operator-2",
        identity_id="identity-1",
        cadence=RepeatCadence(RepeatCadenceUnit.WEEK, 1),
        context=RepeatOrderContext(
            scheduled_for=datetime(2026, 10, 1, 9, tzinfo=UTC),
            service_scope="Погрузка",
            capacity_units=Decimal("1"),
        ),
    )

    with pytest.raises(IntegrityViolation, match="owner scope is immutable"):
        repository.save(plan, expected_revision=1)

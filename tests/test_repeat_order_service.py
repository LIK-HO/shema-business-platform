from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from shema_platform.application.commands import Actor
from shema_platform.application.repeat_order import (
    RepeatOrderService,
    RepeatOrderValidation,
)
from shema_platform.domain.economics import EconomicEntry
from shema_platform.domain.identity import Identity, IdentityState
from shema_platform.domain.money import Money
from shema_platform.domain.order import Order, OrderLine, OrderStatus
from shema_platform.domain.repeat_order import (
    RepeatCadence,
    RepeatCadenceUnit,
    RepeatOrderContext,
)
from shema_platform.foundation.audit import AuditLog
from shema_platform.foundation.authorization import (
    AuthorizationSubject,
    Permission,
    RBACAuthorizer,
)
from shema_platform.foundation.errors import IntegrityViolation, QuarantineRequired
from shema_platform.foundation.idempotency import IdempotencyStore
from shema_platform.foundation.outbox import OutboxStore
from shema_platform.foundation.policy import PolicyEngine


class MemoryIdentityRepository:
    def __init__(self) -> None:
        self.items: dict[str, Identity] = {}

    def get(self, identity_id: str) -> Identity | None:
        return self.items.get(identity_id)

    def find_by_tax_id(self, tax_id: str) -> Identity | None:
        return next((item for item in self.items.values() if item.tax_id == tax_id), None)

    def add(self, identity: Identity) -> None:
        self.items[identity.identity_id] = identity


class MemoryOrderRepository:
    def __init__(self) -> None:
        self.items: dict[str, Order] = {}

    def add(self, order: Order) -> None:
        if order.order_id in self.items:
            raise IntegrityViolation("order already exists")
        self.items[order.order_id] = order

    def get(self, order_id: str) -> Order | None:
        return self.items.get(order_id)

    def save(self, order: Order) -> None:
        current = self.items.get(order.order_id)
        if current is None:
            raise KeyError(order.order_id)
        if current.status is order.status:
            if current.status is not OrderStatus.DRAFT and current.lines != order.lines:
                raise IntegrityViolation("order lines are immutable after draft state")
        elif order.status is OrderStatus.CONFIRMED and current.confirm() == order:
            pass
        else:
            raise IntegrityViolation("unsupported order transition")
        self.items[order.order_id] = order


class MemoryRepeatOrderRepository:
    def __init__(self) -> None:
        self.items = {}

    def add(self, plan) -> None:
        if plan.plan_id in self.items:
            raise IntegrityViolation("repeat plan already exists")
        self.items[plan.plan_id] = plan

    def get(self, plan_id: str):
        return self.items.get(plan_id)

    def save(self, plan, *, expected_revision: int):
        current = self.items.get(plan.plan_id)
        if current is None:
            raise KeyError(plan.plan_id)
        if current.revision != expected_revision:
            raise IntegrityViolation("repeat plan revision conflict")
        if (
            current.source_order_id != plan.source_order_id
            or current.identity_id != plan.identity_id
            or current.cadence != plan.cadence
        ):
            raise IntegrityViolation("repeat plan immutable fields changed")
        saved = replace(plan, revision=current.revision + 1)
        self.items[plan.plan_id] = saved
        return saved


class MemoryEconomicsRepository:
    def __init__(self) -> None:
        self.items: list[EconomicEntry] = []

    def add(self, entry: EconomicEntry) -> None:
        self.items.append(entry)

    def list_for_entity(self, entity_ref: str):
        return tuple(item for item in self.items if item.entity_ref == entity_ref)


class MemoryUoW:
    def __init__(self, identity, order, repeat, economics, idempotency, audit, outbox) -> None:
        self.identities = identity
        self.orders = order
        self.repeat_orders = repeat
        self.economics = economics
        self.idempotency = idempotency
        self.audits = audit
        self.outbox = outbox
        self.evidence = None
        self.quarantine = None
        self.jobs = None
        self.commercial_actions = None
        self.ai_runs = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class StaticRevalidator:
    def __init__(self, *, price: Decimal = Decimal("1500")) -> None:
        self.price = price

    def validate(self, *, identity, order, plan) -> RepeatOrderValidation:
        return RepeatOrderValidation(
            counterparty_ok=identity.state in {IdentityState.VERIFIED, IdentityState.ACTIVE},
            service_scope_ok=True,
            pricing_ok=True,
            date_capacity_ok=True,
            evidence_fresh_ok=True,
            resolved_lines=(
                OrderLine(
                    "repeat-line-1",
                    plan.context.service_scope,
                    plan.context.capacity_units,
                    Money(self.price, "RUB"),
                ),
            ),
        )


def make_service(*, revalidator: StaticRevalidator | None = None, ids=None):
    identity_repo = MemoryIdentityRepository()
    identity_repo.add(
        Identity(
            "identity-1",
            "ООО Repeat",
            IdentityState.VERIFIED,
            tax_id="7700000000",
        )
    )
    order_repo = MemoryOrderRepository()
    order_repo.add(
        Order(
            "source-order",
            "identity-1",
            "action-1",
            (
                OrderLine(
                    "source-line",
                    "Погрузка",
                    Decimal("2"),
                    Money(1500, "RUB"),
                ),
            ),
            status=OrderStatus.COMPLETED,
        )
    )
    repeat_repo = MemoryRepeatOrderRepository()
    economics_repo = MemoryEconomicsRepository()
    idempotency = IdempotencyStore()
    audit = AuditLog()
    outbox = OutboxStore()
    uow = MemoryUoW(
        identity_repo,
        order_repo,
        repeat_repo,
        economics_repo,
        idempotency,
        audit,
        outbox,
    )

    next_ids = iter(ids or ["repeat-order-1"])
    return (
        RepeatOrderService(
            lambda: uow,
            RBACAuthorizer(
                (
                    AuthorizationSubject(
                        "operator-1",
                        frozenset({Permission.ORDER_CREATE}),
                    ),
                )
            ),
            PolicyEngine(),
            revalidator or StaticRevalidator(),
            id_factory=lambda: next(next_ids),
            clock=lambda: datetime(2026, 9, 28, 9, tzinfo=UTC),
        ),
        uow,
    )


def actor() -> Actor:
    return Actor("operator-1", trust_level=2)


def context() -> RepeatOrderContext:
    return RepeatOrderContext(
        scheduled_for=datetime(2026, 10, 1, 9, tzinfo=UTC),
        service_scope="Погрузка",
        capacity_units=Decimal("2"),
    )


def test_repeat_order_lifecycle_preserves_source_and_records_economics() -> None:
    service, uow = make_service()

    plan = service.create_plan(
        plan_id="plan-1",
        source_order_id="source-order",
        actor=actor(),
        cadence=RepeatCadence(RepeatCadenceUnit.WEEK, 1),
        context=context(),
        request_hash="plan-hash",
        idempotency_key="plan-idem",
        correlation_id="corr-3a",
    )
    draft = service.create_next_repeat_order(
        actor=actor(),
        plan_id=plan.plan_id,
        request_hash="create-hash",
        idempotency_key="create-idem",
        correlation_id="corr-3a",
    )
    confirmed = service.confirm_repeat_order(
        actor=actor(),
        plan_id=plan.plan_id,
        order_id=draft.order_id,
        request_hash="confirm-hash",
        idempotency_key="confirm-idem",
        correlation_id="corr-3a",
    )

    source = uow.orders.get("source-order")
    stored_plan = uow.repeat_orders.get("plan-1")
    assert source is not None
    assert source.status is OrderStatus.COMPLETED
    assert confirmed.status is OrderStatus.CONFIRMED
    assert stored_plan is not None
    assert stored_plan.last_order_id == confirmed.order_id
    assert stored_plan.pending_order_id is None
    assert stored_plan.context.scheduled_for == datetime(
        2026, 10, 8, 9, tzinfo=UTC
    )
    assert uow.economics.list_for_entity(confirmed.order_id)[0].amount.amount == Decimal("3000")
    assert [record.action for record in uow.audits.all()] == [
        "repeat_order.plan_created",
        "repeat_order.created",
        "repeat_order.confirmed",
    ]
    assert len(uow.outbox.pending()) == 3


def test_repeat_order_create_is_idempotent_and_duplicate_window_is_blocked() -> None:
    service, _ = make_service()

    plan = service.create_plan(
        plan_id="plan-1",
        source_order_id="source-order",
        actor=actor(),
        cadence=RepeatCadence(RepeatCadenceUnit.DAY),
        context=context(),
        request_hash="plan-hash",
        idempotency_key="plan-idem",
    )
    first = service.create_next_repeat_order(
        actor=actor(),
        plan_id=plan.plan_id,
        request_hash="create-hash",
        idempotency_key="create-idem",
    )
    repeated = service.create_next_repeat_order(
        actor=actor(),
        plan_id=plan.plan_id,
        request_hash="create-hash",
        idempotency_key="create-idem",
    )
    assert repeated == first

    with pytest.raises(IntegrityViolation, match="pending order"):
        service.create_next_repeat_order(
            actor=actor(),
            plan_id=plan.plan_id,
            request_hash="different-hash",
            idempotency_key="second-create-idem",
        )


def test_confirmation_revalidates_current_price_before_commit() -> None:
    service, _ = make_service()
    plan = service.create_plan(
        plan_id="plan-1",
        source_order_id="source-order",
        actor=actor(),
        cadence=RepeatCadence(RepeatCadenceUnit.WEEK),
        context=context(),
        request_hash="plan-hash",
        idempotency_key="plan-idem",
    )
    draft = service.create_next_repeat_order(
        actor=actor(),
        plan_id=plan.plan_id,
        request_hash="create-hash",
        idempotency_key="create-idem",
    )

    service_with_changed_price, _ = make_service(
        revalidator=StaticRevalidator(price=Decimal("1700")),
    )
    # Reuse the same in-memory state to model the price policy changing between
    # creation and confirmation.
    service_with_changed_price._unit_of_work_factory = service._unit_of_work_factory

    with pytest.raises(QuarantineRequired, match="pricing"):
        service_with_changed_price.confirm_repeat_order(
            actor=actor(),
            plan_id=plan.plan_id,
            order_id=draft.order_id,
            request_hash="confirm-hash",
            idempotency_key="confirm-idem",
        )


def test_repeat_plan_controls_pause_skip_resume_cancel_and_context_edit() -> None:
    service, uow = make_service()

    service.create_plan(
        plan_id="plan-1",
        source_order_id="source-order",
        actor=actor(),
        cadence=RepeatCadence(RepeatCadenceUnit.WEEK),
        context=context(),
        request_hash="plan-hash",
        idempotency_key="plan-idem",
    )
    paused = service.pause_plan(
        actor=actor(),
        plan_id="plan-1",
        request_hash="pause-hash",
        idempotency_key="pause-idem",
    )
    assert paused.status.value == "paused"

    resumed = service.resume_plan(
        actor=actor(),
        plan_id="plan-1",
        request_hash="resume-hash",
        idempotency_key="resume-idem",
    )
    assert resumed.status.value == "active"

    edited = service.edit_context(
        actor=actor(),
        plan_id="plan-1",
        context=RepeatOrderContext(
            scheduled_for=datetime(2026, 10, 2, 9, tzinfo=UTC),
            service_scope="Подъём оборудования",
            capacity_units=Decimal("3"),
        ),
        request_hash="edit-hash",
        idempotency_key="edit-idem",
    )
    assert edited.context.service_scope == "Подъём оборудования"

    skipped = service.skip_once(
        actor=actor(),
        plan_id="plan-1",
        request_hash="skip-hash",
        idempotency_key="skip-idem",
    )
    assert skipped.skipped_occurrences == 1
    assert skipped.context.scheduled_for == datetime(2026, 10, 9, 9, tzinfo=UTC)

    skipped_again = service.skip_once(
        actor=actor(),
        plan_id="plan-1",
        request_hash="skip-hash-2",
        idempotency_key="skip-idem-2",
    )
    assert skipped_again.skipped_occurrences == 2
    assert skipped_again.context.scheduled_for == datetime(2026, 10, 16, 9, tzinfo=UTC)

    assert len(uow.outbox.pending()) == 6
    assert len(uow.audits.all()) == 6

    cancelled = service.cancel_plan(
        actor=actor(),
        plan_id="plan-1",
        request_hash="cancel-hash",
        idempotency_key="cancel-idem",
    )
    assert cancelled.status.value == "cancelled"
    assert uow.repeat_orders.get("plan-1") == cancelled


def test_repeat_plan_rejects_unverified_identity() -> None:
    service, uow = make_service()
    uow.identities.items["identity-1"] = Identity(
        "identity-1",
        "ООО Repeat",
        IdentityState.UNKNOWN,
    )

    with pytest.raises(QuarantineRequired, match="verified identity"):
        service.create_plan(
            plan_id="plan-1",
            source_order_id="source-order",
            actor=actor(),
            cadence=RepeatCadence(RepeatCadenceUnit.DAY),
            context=context(),
            request_hash="plan-hash",
            idempotency_key="plan-idem",
        )

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import NAMESPACE_URL, uuid4, uuid5

from shema_platform.application.commands import Actor
from shema_platform.application.ports import UnitOfWork
from shema_platform.domain.economics import EconomicEntry, EconomicKind
from shema_platform.domain.identity import Identity
from shema_platform.domain.order import Order, OrderLine, OrderStatus
from shema_platform.domain.repeat_order import (
    RepeatCadence,
    RepeatOrderContext,
    RepeatOrderPlan,
    RepeatPlanStatus,
)
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.authorization import Permission, RBACAuthorizer
from shema_platform.foundation.errors import (
    IdempotencyConflict,
    IntegrityViolation,
    PolicyDenied,
    QuarantineRequired,
)
from shema_platform.foundation.outbox import OutboxEvent
from shema_platform.foundation.policy import Decision, PolicyContext, PolicyEngine


@dataclass(frozen=True, slots=True)
class RepeatOrderValidation:
    counterparty_ok: bool
    service_scope_ok: bool
    pricing_ok: bool
    date_capacity_ok: bool
    evidence_fresh_ok: bool
    resolved_lines: tuple[OrderLine, ...]
    failure_reasons: tuple[str, ...] = ()

    @property
    def approved(self) -> bool:
        return (
            self.counterparty_ok
            and self.service_scope_ok
            and self.pricing_ok
            and self.date_capacity_ok
            and self.evidence_fresh_ok
            and bool(self.resolved_lines)
        )

    def describe_failure(self) -> str:
        failures = list(self.failure_reasons)
        if not self.counterparty_ok:
            failures.append("counterparty_identity_or_status")
        if not self.service_scope_ok:
            failures.append("service_scope")
        if not self.pricing_ok:
            failures.append("current_pricing_or_policy")
        if not self.date_capacity_ok:
            failures.append("date_or_capacity_assumptions")
        if not self.evidence_fresh_ok:
            failures.append("evidence_freshness")
        if not self.resolved_lines:
            failures.append("resolved_order_lines")
        return ", ".join(dict.fromkeys(failures)) or "repeat_order_validation_failed"


class RepeatOrderRevalidator(Protocol):
    def validate(
        self,
        *,
        identity: Identity,
        order: Order,
        plan: RepeatOrderPlan,
    ) -> RepeatOrderValidation: ...


def _default_id() -> str:
    return str(uuid4())


class RepeatOrderService:
    """Bounded repeat-order application workflow before Bitrix24 cutover."""

    def __init__(
        self,
        unit_of_work_factory: Callable[[], UnitOfWork],
        authorizer: RBACAuthorizer,
        policy: PolicyEngine,
        revalidator: RepeatOrderRevalidator,
        *,
        id_factory: Callable[[], str] = _default_id,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._authorizer = authorizer
        self._policy = policy
        self._revalidator = revalidator
        self._id_factory = id_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def create_plan(
        self,
        *,
        plan_id: str,
        source_order_id: str,
        actor: Actor,
        cadence: RepeatCadence,
        context: RepeatOrderContext,
        request_hash: str,
        idempotency_key: str,
        correlation_id: str | None = None,
    ) -> RepeatOrderPlan:
        with self._unit_of_work_factory() as uow:
            existing = self._existing_plan(uow, idempotency_key, request_hash)
            if existing is not None:
                return existing

            source = uow.orders.get(source_order_id)
            if source is None:
                raise KeyError(f"unknown source order: {source_order_id}")
            if source.status is not OrderStatus.COMPLETED:
                raise QuarantineRequired(
                    "repeat plan requires a completed source order"
                )

            identity = self._verified_identity(uow, source.identity_id)
            self._authorize(actor, identity, evidence_level=2)

            reservation = uow.idempotency.reserve(
                key=idempotency_key,
                request_hash=request_hash,
                result_ref=plan_id,
            )
            if reservation.result_ref != plan_id:
                stored = uow.repeat_orders.get(reservation.result_ref)
                if stored is None:
                    raise IntegrityViolation(
                        "idempotency reservation references missing repeat plan"
                    )
                return stored

            plan = RepeatOrderPlan(
                plan_id=plan_id,
                source_order_id=source_order_id,
                identity_id=source.identity_id,
                cadence=cadence,
                context=context,
            )
            uow.repeat_orders.add(plan)
            self._record(
                uow,
                actor=actor,
                action="repeat_order.plan_created",
                resource_type="repeat_order_plan",
                resource_id=plan.plan_id,
                metadata={
                    "source_order_id": plan.source_order_id,
                    "identity_id": plan.identity_id,
                    "cadence": plan.cadence.unit.value,
                    "interval": plan.cadence.interval,
                },
                correlation_id=correlation_id,
            )
            self._event(
                uow,
                event_type="repeat_order.plan_created",
                aggregate_type="repeat_order_plan",
                aggregate_id=plan.plan_id,
                payload={
                    "plan_id": plan.plan_id,
                    "source_order_id": plan.source_order_id,
                    "identity_id": plan.identity_id,
                },
            )
            return plan

    def create_next_repeat_order(
        self,
        *,
        actor: Actor,
        plan_id: str,
        request_hash: str,
        idempotency_key: str,
        correlation_id: str | None = None,
    ) -> Order:
        with self._unit_of_work_factory() as uow:
            existing = self._existing_order(uow, idempotency_key, request_hash)
            if existing is not None:
                return existing

            plan = self._require_plan(uow, plan_id)
            if plan.status is not RepeatPlanStatus.ACTIVE:
                raise QuarantineRequired("repeat plan is not active")
            if plan.pending_order_id is not None:
                raise IntegrityViolation(
                    "repeat plan already has a pending order"
                )

            source = uow.orders.get(plan.source_order_id)
            if source is None:
                raise IntegrityViolation("repeat plan references missing source order")
            if source.status is not OrderStatus.COMPLETED:
                raise QuarantineRequired(
                    "repeat source order is no longer completed"
                )

            identity = self._verified_identity(uow, plan.identity_id)
            validation = self._revalidator.validate(
                identity=identity,
                order=source,
                plan=plan,
            )
            self._authorize(
                actor,
                identity,
                evidence_level=2 if validation.evidence_fresh_ok else 0,
            )
            self._require_validation(validation)

            order_id = self._id_factory()
            reservation = uow.idempotency.reserve(
                key=idempotency_key,
                request_hash=request_hash,
                result_ref=order_id,
            )
            if reservation.result_ref != order_id:
                stored = uow.orders.get(reservation.result_ref)
                if stored is None:
                    raise IntegrityViolation(
                        "idempotency reservation references missing repeat order"
                    )
                return stored

            order = Order(
                order_id=order_id,
                identity_id=source.identity_id,
                source_action_id=source.source_action_id,
                lines=tuple(validation.resolved_lines),
                status=OrderStatus.DRAFT,
            )
            uow.orders.add(order)
            updated_plan = plan.attach_pending_order(order.order_id)
            uow.repeat_orders.save(
                updated_plan,
                expected_revision=plan.revision,
            )

            self._record(
                uow,
                actor=actor,
                action="repeat_order.created",
                resource_type="order",
                resource_id=order.order_id,
                metadata={
                    "plan_id": plan.plan_id,
                    "source_order_id": plan.source_order_id,
                    "identity_id": order.identity_id,
                },
                correlation_id=correlation_id,
            )
            self._event(
                uow,
                event_type="repeat_order.created",
                aggregate_type="order",
                aggregate_id=order.order_id,
                payload={
                    "order_id": order.order_id,
                    "plan_id": plan.plan_id,
                    "source_order_id": plan.source_order_id,
                    "status": order.status.value,
                },
            )
            return order

    def confirm_repeat_order(
        self,
        *,
        actor: Actor,
        plan_id: str,
        order_id: str,
        request_hash: str,
        idempotency_key: str,
        correlation_id: str | None = None,
    ) -> Order:
        with self._unit_of_work_factory() as uow:
            existing = self._existing_order(uow, idempotency_key, request_hash)
            if existing is not None:
                return existing

            plan = self._require_plan(uow, plan_id)
            if plan.pending_order_id != order_id:
                raise IntegrityViolation(
                    "order is not the pending repeat order for this plan"
                )
            if plan.status is RepeatPlanStatus.CANCELLED:
                # Cancelling the recurrence does not cancel an already-created order.
                pass

            order = uow.orders.get(order_id)
            if order is None:
                raise IntegrityViolation("repeat plan references missing pending order")
            if order.status is not OrderStatus.DRAFT:
                raise QuarantineRequired("only a draft repeat order can be confirmed")

            identity = self._verified_identity(uow, plan.identity_id)
            validation = self._revalidator.validate(
                identity=identity,
                order=order,
                plan=plan,
            )
            self._authorize(
                actor,
                identity,
                evidence_level=2 if validation.evidence_fresh_ok else 0,
            )
            self._require_validation(validation)

            if tuple(validation.resolved_lines) != tuple(order.lines):
                raise QuarantineRequired(
                    "current pricing or repeat context changed; "
                    "recreate the draft before confirmation"
                )

            reservation = uow.idempotency.reserve(
                key=idempotency_key,
                request_hash=request_hash,
                result_ref=order_id,
            )
            if reservation.result_ref != order_id:
                stored = uow.orders.get(reservation.result_ref)
                if stored is None:
                    raise IntegrityViolation(
                        "idempotency reservation references missing confirmed order"
                    )
                return stored

            confirmed = order.confirm()
            uow.orders.save(confirmed)
            uow.economics.add(
                EconomicEntry(
                    entry_id=f"economics:repeat-order:{order_id}:revenue",
                    entity_ref=order_id,
                    kind=EconomicKind.REVENUE,
                    amount=confirmed.total,
                    source_ref=f"repeat-order:{plan_id}:confirm",
                    occurred_at=self._clock(),
                )
            )
            updated_plan = plan.mark_order_confirmed(order_id)
            uow.repeat_orders.save(
                updated_plan,
                expected_revision=plan.revision,
            )

            self._record(
                uow,
                actor=actor,
                action="repeat_order.confirmed",
                resource_type="order",
                resource_id=order_id,
                metadata={
                    "plan_id": plan_id,
                    "identity_id": confirmed.identity_id,
                    "status": confirmed.status.value,
                    "revenue": str(confirmed.total.amount),
                },
                correlation_id=correlation_id,
            )
            self._event(
                uow,
                event_type="repeat_order.confirmed",
                aggregate_type="order",
                aggregate_id=order_id,
                payload={
                    "order_id": order_id,
                    "plan_id": plan_id,
                    "status": confirmed.status.value,
                    "revenue": str(confirmed.total.amount),
                },
            )
            return confirmed

    def pause_plan(
        self,
        *,
        actor: Actor,
        plan_id: str,
        request_hash: str,
        idempotency_key: str,
        correlation_id: str | None = None,
    ) -> RepeatOrderPlan:
        return self._mutate_plan(
            actor=actor,
            plan_id=plan_id,
            request_hash=request_hash,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            transition=lambda plan: plan.pause(),
            action="repeat_order.plan_paused",
        )

    def resume_plan(
        self,
        *,
        actor: Actor,
        plan_id: str,
        request_hash: str,
        idempotency_key: str,
        correlation_id: str | None = None,
    ) -> RepeatOrderPlan:
        return self._mutate_plan(
            actor=actor,
            plan_id=plan_id,
            request_hash=request_hash,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            transition=lambda plan: plan.resume(),
            action="repeat_order.plan_resumed",
        )

    def skip_once(
        self,
        *,
        actor: Actor,
        plan_id: str,
        request_hash: str,
        idempotency_key: str,
        correlation_id: str | None = None,
    ) -> RepeatOrderPlan:
        return self._mutate_plan(
            actor=actor,
            plan_id=plan_id,
            request_hash=request_hash,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            transition=lambda plan: plan.skip_once(),
            action="repeat_order.plan_skipped",
        )

    def cancel_plan(
        self,
        *,
        actor: Actor,
        plan_id: str,
        request_hash: str,
        idempotency_key: str,
        correlation_id: str | None = None,
    ) -> RepeatOrderPlan:
        return self._mutate_plan(
            actor=actor,
            plan_id=plan_id,
            request_hash=request_hash,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            transition=lambda plan: plan.cancel(),
            action="repeat_order.plan_cancelled",
        )

    def edit_context(
        self,
        *,
        actor: Actor,
        plan_id: str,
        context: RepeatOrderContext,
        request_hash: str,
        idempotency_key: str,
        correlation_id: str | None = None,
    ) -> RepeatOrderPlan:
        return self._mutate_plan(
            actor=actor,
            plan_id=plan_id,
            request_hash=request_hash,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            transition=lambda plan: plan.edit_context(context),
            action="repeat_order.plan_context_edited",
        )

    def _mutate_plan(
        self,
        *,
        actor: Actor,
        plan_id: str,
        request_hash: str,
        idempotency_key: str,
        correlation_id: str | None,
        transition: Callable[[RepeatOrderPlan], RepeatOrderPlan],
        action: str,
    ) -> RepeatOrderPlan:
        with self._unit_of_work_factory() as uow:
            existing = self._existing_plan(uow, idempotency_key, request_hash)
            if existing is not None:
                return existing

            plan = self._require_plan(uow, plan_id)
            identity = self._verified_identity(uow, plan.identity_id)
            self._authorize(actor, identity, evidence_level=2)

            reservation = uow.idempotency.reserve(
                key=idempotency_key,
                request_hash=request_hash,
                result_ref=plan_id,
            )
            if reservation.result_ref != plan_id:
                stored = uow.repeat_orders.get(reservation.result_ref)
                if stored is None:
                    raise IntegrityViolation(
                        "idempotency reservation references missing repeat plan"
                    )
                return stored

            updated = transition(plan)
            uow.repeat_orders.save(updated, expected_revision=plan.revision)
            self._record(
                uow,
                actor=actor,
                action=action,
                resource_type="repeat_order_plan",
                resource_id=plan_id,
                metadata={
                    "previous_revision": plan.revision,
                    "new_status": updated.status.value,
                    "pending_order_id": updated.pending_order_id,
                },
                correlation_id=correlation_id,
            )
            self._event(
                uow,
                event_type=action,
                aggregate_type="repeat_order_plan",
                aggregate_id=plan_id,
                payload={
                    "plan_id": plan_id,
                    "status": updated.status.value,
                    "revision": updated.revision,
                },
            )
            return updated

    @staticmethod
    def _require_validation(validation: RepeatOrderValidation) -> None:
        if not validation.approved:
            raise QuarantineRequired(
                "repeat order validation failed: " + validation.describe_failure()
            )

    @staticmethod
    def _require_plan(uow: UnitOfWork, plan_id: str) -> RepeatOrderPlan:
        plan = uow.repeat_orders.get(plan_id)
        if plan is None:
            raise KeyError(f"unknown repeat plan: {plan_id}")
        return plan

    @staticmethod
    def _verified_identity(uow: UnitOfWork, identity_id: str) -> Identity:
        identity = uow.identities.get(identity_id)
        if identity is None:
            raise IntegrityViolation(
                "repeat order references missing counterparty identity"
            )
        identity.require_verified()
        return identity

    def _authorize(self, actor: Actor, identity: Identity, *, evidence_level: int) -> None:
        self._authorizer.require(actor.actor_id, Permission.ORDER_CREATE)
        decision = self._policy.evaluate(
            PolicyContext(
                actor_id=actor.actor_id,
                action="order_create",
                resource_type="identity",
                resource_id=identity.identity_id,
                actor_trust_level=actor.trust_level,
                resource_trust_level=2,
                evidence_level=evidence_level,
            )
        )
        if decision.decision is Decision.DENY:
            raise PolicyDenied(decision.reason)
        if decision.decision is not Decision.ALLOW:
            raise QuarantineRequired(decision.reason)

    @staticmethod
    def _existing_plan(
        uow: UnitOfWork,
        idempotency_key: str,
        request_hash: str,
    ) -> RepeatOrderPlan | None:
        existing = uow.idempotency.get(idempotency_key)
        if existing is None:
            return None
        if existing.request_hash != request_hash:
            raise IdempotencyConflict(
                "idempotency key reused with different request"
            )
        plan = uow.repeat_orders.get(existing.result_ref)
        if plan is None:
            raise IntegrityViolation(
                "idempotency record references missing repeat plan"
            )
        return plan

    @staticmethod
    def _existing_order(
        uow: UnitOfWork,
        idempotency_key: str,
        request_hash: str,
    ) -> Order | None:
        existing = uow.idempotency.get(idempotency_key)
        if existing is None:
            return None
        if existing.request_hash != request_hash:
            raise IdempotencyConflict(
                "idempotency key reused with different request"
            )
        order = uow.orders.get(existing.result_ref)
        if order is None:
            raise IntegrityViolation(
                "idempotency record references missing repeat order"
            )
        return order

    def _record(
        self,
        uow: UnitOfWork,
        *,
        actor: Actor,
        action: str,
        resource_type: str,
        resource_id: str,
        metadata: dict[str, object],
        correlation_id: str | None,
    ) -> None:
        uow.audits.append(
            AuditRecord(
                audit_id=str(uuid5(NAMESPACE_URL, f"{action}:{resource_id}")),
                actor_id=actor.actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                outcome="success",
                occurred_at=self._clock(),
                metadata=metadata,
                correlation_id=correlation_id,
            )
        )

    def _event(
        self,
        uow: UnitOfWork,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict[str, object],
    ) -> None:
        event_key = f"{event_type}:{aggregate_id}"
        uow.outbox.append(
            OutboxEvent(
                event_id=str(uuid5(NAMESPACE_URL, event_key)),
                event_type=event_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                payload=payload,
                occurred_at=self._clock(),
            )
        )

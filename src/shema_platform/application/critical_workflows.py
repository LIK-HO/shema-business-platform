from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from shema_platform.application.commands import Actor
from shema_platform.application.commercial_action import CommercialActionService
from shema_platform.application.order import OrderService
from shema_platform.application.ports import UnitOfWork
from shema_platform.domain.commercial_action import CommercialAction
from shema_platform.domain.order import Order, OrderLine
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.authorization import Permission, RBACAuthorizer
from shema_platform.foundation.errors import (
    IdempotencyConflict,
    IntegrityViolation,
)
from shema_platform.foundation.outbox import OutboxEvent
from shema_platform.foundation.policy import PolicyEngine


class CommercialActionCreateWorkflow:
    """Canonical transactional workflow for creating a ready commercial action."""

    def __init__(
        self,
        unit_of_work_factory: Callable[[], UnitOfWork],
        authorizer: RBACAuthorizer,
        policy: PolicyEngine,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._authorizer = authorizer
        self._policy = policy

    def execute(
        self,
        *,
        action_id: str,
        actor: Actor,
        identity_id: str,
        contact_ref: str,
        channel: str,
        evidence_refs: tuple[str, ...],
        request_hash: str,
        idempotency_key: str,
        correlation_id: str | None = None,
    ) -> CommercialAction:
        with self._unit_of_work_factory() as uow:
            existing = uow.idempotency.get(idempotency_key)
            if existing is not None:
                if existing.request_hash != request_hash:
                    raise IdempotencyConflict(
                        "idempotency key reused with different request"
                    )
                action = uow.commercial_actions.get(existing.result_ref)
                if action is None:
                    raise IntegrityViolation(
                        "idempotency record references missing commercial action"
                    )
                return action

            identity = uow.identities.get(identity_id)
            if identity is None:
                raise KeyError(f"unknown identity: {identity_id}")

            service = CommercialActionService(
                self._authorizer,
                self._policy,
                uow.idempotency,
            )
            action = service.create_ready(
                action_id=action_id,
                actor=actor,
                identity=identity,
                contact_ref=contact_ref,
                channel=channel,
                evidence_refs=evidence_refs,
                request_hash=request_hash,
                idempotency_key=idempotency_key,
            )
            uow.commercial_actions.add(action)

            occurred_at = datetime.now(UTC)
            event_key = f"commercial-action.created:{action_id}"
            uow.outbox.append(
                OutboxEvent(
                    event_id=str(uuid5(NAMESPACE_URL, event_key)),
                    event_type="commercial_action.created",
                    aggregate_type="commercial_action",
                    aggregate_id=action_id,
                    payload={
                        "action_id": action_id,
                        "identity_id": action.identity_id,
                        "channel": action.channel,
                        "status": action.status.value,
                    },
                    occurred_at=occurred_at,
                )
            )
            uow.audits.append(
                AuditRecord(
                    audit_id=str(uuid5(NAMESPACE_URL, f"audit:{event_key}")),
                    actor_id=actor.actor_id,
                    action="commercial_action.created",
                    resource_type="commercial_action",
                    resource_id=action_id,
                    outcome="success",
                    occurred_at=occurred_at,
                    metadata={
                        "identity_id": action.identity_id,
                        "channel": action.channel,
                    },
                    correlation_id=correlation_id,
                )
            )
            return action


class OrderCreateWorkflow:
    """Canonical transactional workflow for creating an order from a sent action."""

    def __init__(
        self,
        unit_of_work_factory: Callable[[], UnitOfWork],
        authorizer: RBACAuthorizer,
        policy: PolicyEngine,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._authorizer = authorizer
        self._policy = policy

    def execute(
        self,
        *,
        order_id: str,
        actor: Actor,
        action_id: str,
        lines: Sequence[OrderLine],
        request_hash: str,
        idempotency_key: str,
        correlation_id: str | None = None,
    ) -> Order:
        with self._unit_of_work_factory() as uow:
            existing = uow.idempotency.get(idempotency_key)
            if existing is not None:
                if existing.request_hash != request_hash:
                    raise IdempotencyConflict(
                        "idempotency key reused with different request"
                    )
                order = uow.orders.get(existing.result_ref)
                if order is None:
                    raise IntegrityViolation(
                        "idempotency record references missing order"
                    )
                return order

            action = uow.commercial_actions.get(action_id)
            if action is None:
                raise KeyError(f"unknown commercial action: {action_id}")

            service = OrderService(
                self._authorizer,
                self._policy,
                uow.idempotency,
            )
            order = service.create_from_action(
                order_id=order_id,
                actor=actor,
                action=action,
                lines=tuple(lines),
                request_hash=request_hash,
                idempotency_key=idempotency_key,
            )
            uow.orders.add(order)

            occurred_at = datetime.now(UTC)
            event_key = f"order.created:{order_id}"
            uow.outbox.append(
                OutboxEvent(
                    event_id=str(uuid5(NAMESPACE_URL, event_key)),
                    event_type="order.created",
                    aggregate_type="order",
                    aggregate_id=order_id,
                    payload={
                        "order_id": order_id,
                        "identity_id": order.identity_id,
                        "source_action_id": order.source_action_id,
                        "status": order.status.value,
                    },
                    occurred_at=occurred_at,
                )
            )
            uow.audits.append(
                AuditRecord(
                    audit_id=str(uuid5(NAMESPACE_URL, f"audit:{event_key}")),
                    actor_id=actor.actor_id,
                    action="order.created",
                    resource_type="order",
                    resource_id=order_id,
                    outcome="success",
                    occurred_at=occurred_at,
                    metadata={
                        "identity_id": order.identity_id,
                        "source_action_id": order.source_action_id,
                    },
                    correlation_id=correlation_id,
                )
            )
            return order

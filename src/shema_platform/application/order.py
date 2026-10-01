from __future__ import annotations

from collections.abc import Sequence

from shema_platform.application.commands import Actor
from shema_platform.domain.commercial_action import CommercialAction, CommercialActionStatus
from shema_platform.domain.order import Order, OrderLine
from shema_platform.foundation.authorization import Permission, RBACAuthorizer
from shema_platform.foundation.errors import PolicyDenied, QuarantineRequired
from shema_platform.foundation.policy import Decision, PolicyContext, PolicyEngine


class OrderService:
    """Creates orders only from an externally sent commercial action."""

    def __init__(
        self,
        authorizer: RBACAuthorizer,
        policy: PolicyEngine,
    ) -> None:
        self._authorizer = authorizer
        self._policy = policy

    def create_from_action(
        self,
        *,
        order_id: str,
        actor: Actor,
        action: CommercialAction,
        lines: Sequence[OrderLine],
        request_hash: str,
    ) -> Order:
        self._authorizer.require(actor.actor_id, Permission.ORDER_CREATE)

        if action.status not in {
            CommercialActionStatus.SENT,
            CommercialActionStatus.COMPLETED,
        }:
            raise QuarantineRequired(
                "order requires a sent or completed commercial action"
            )

        action.validate_for_send()

        decision = self._policy.evaluate(
            PolicyContext(
                actor_id=actor.actor_id,
                action="order_create",
                resource_type="identity",
                resource_id=action.identity_id,
                actor_trust_level=actor.trust_level,
                resource_trust_level=2,
                evidence_level=2 if action.evidence_refs else 0,
            )
        )
        if decision.decision is not Decision.ALLOW:
            raise PolicyDenied(decision.reason)

        order = Order(
            order_id=order_id,
            identity_id=action.identity_id,
            source_action_id=action.action_id,
            lines=tuple(lines),
        )
        return order

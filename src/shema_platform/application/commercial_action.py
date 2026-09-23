from __future__ import annotations

from shema_platform.application.commands import Actor
from shema_platform.domain.commercial_action import CommercialAction
from shema_platform.domain.identity import Identity
from shema_platform.foundation.authorization import Permission, RBACAuthorizer
from shema_platform.foundation.errors import PolicyDenied
from shema_platform.foundation.policy import Decision, PolicyContext, PolicyEngine


class CommercialActionService:
    """Create a ready-to-send action without performing an external side effect."""

    def __init__(
        self,
        authorizer: RBACAuthorizer,
        policy: PolicyEngine,
    ) -> None:
        self._authorizer = authorizer
        self._policy = policy

    def create_ready(
        self,
        *,
        action_id: str,
        actor: Actor,
        identity: Identity,
        contact_ref: str,
        channel: str,
        evidence_refs: tuple[str, ...],
        request_hash: str,
    ) -> CommercialAction:
        self._authorizer.require(
            actor.actor_id,
            Permission.COMMERCIAL_ACTION_CREATE,
        )
        identity.require_verified()

        decision = self._policy.evaluate(
            PolicyContext(
                actor_id=actor.actor_id,
                action="commercial_action",
                resource_type="identity",
                resource_id=identity.identity_id,
                actor_trust_level=actor.trust_level,
                resource_trust_level=2,
                evidence_level=2 if evidence_refs else 0,
            )
        )
        if decision.decision is not Decision.ALLOW:
            raise PolicyDenied(decision.reason)

        action = CommercialAction(
            action_id=action_id,
            identity_id=identity.identity_id,
            contact_ref=contact_ref,
            channel=channel,
            evidence_refs=evidence_refs,
        ).mark_ready()

        return action

from __future__ import annotations

from dataclasses import dataclass

from shema_platform.application.ports import IdempotencyRepository
from shema_platform.domain.identity import Identity
from shema_platform.foundation.authorization import Permission, RBACAuthorizer
from shema_platform.foundation.errors import AuthorizationError, PolicyDenied
from shema_platform.foundation.policy import Decision, PolicyContext, PolicyEngine


@dataclass(frozen=True, slots=True)
class Actor:
    actor_id: str
    trust_level: int
    permissions: frozenset[Permission] = frozenset()

    def authorization_subject(self):
        from shema_platform.foundation.authorization import AuthorizationSubject

        return AuthorizationSubject.from_actor(
            actor_id=self.actor_id,
            permissions=self.permissions,
        )


@dataclass(frozen=True, slots=True)
class CommercialActionCommand:
    command_id: str
    actor: Actor
    identity: Identity
    evidence_level: int
    request_hash: str


class CommandService:
    """Critical command boundary: authorization → policy → idempotency → execution."""

    def __init__(
        self,
        policy: PolicyEngine,
        idempotency: IdempotencyRepository,
        authorizer: RBACAuthorizer,
    ) -> None:
        self._policy = policy
        self._idempotency = idempotency
        self._authorizer = authorizer

    def authorize(self, command: CommercialActionCommand) -> None:
        if not command.actor.actor_id:
            raise AuthorizationError("actor is required")
        self._authorizer.require(
            command.actor.actor_id,
            Permission.COMMERCIAL_ACTION_CREATE,
        )

    def execute(self, command: CommercialActionCommand) -> str:
        self.authorize(command)
        command.identity.require_verified()

        decision = self._policy.evaluate(
            PolicyContext(
                actor_id=command.actor.actor_id,
                action="commercial_action",
                resource_type="identity",
                resource_id=command.identity.identity_id,
                actor_trust_level=command.actor.trust_level,
                resource_trust_level=2,
                evidence_level=command.evidence_level,
            )
        )
        if decision.decision is not Decision.ALLOW:
            raise PolicyDenied(decision.reason)

        return self._idempotency.reserve(
            key=command.command_id,
            request_hash=command.request_hash,
            result_ref=command.identity.identity_id,
        ).result_ref

from __future__ import annotations

from dataclasses import dataclass

from shema_platform.foundation.errors import AuthorizationError, PolicyDenied
from shema_platform.foundation.idempotency import IdempotencyStore
from shema_platform.foundation.policy import Decision, PolicyContext, PolicyEngine


@dataclass(frozen=True, slots=True)
class Actor:
    actor_id: str
    trusted_level: int


@dataclass(frozen=True, slots=True)
class CommercialActionCommand:
    command_id: str
    actor: Actor
    identity_id: str
    evidence_level: int
    request_hash: str


class CommandService:
    """Canonical command boundary: authorization → policy → idempotency → execution."""

    def __init__(self, policy: PolicyEngine, idempotency: IdempotencyStore) -> None:
        self._policy = policy
        self._idempotency = idempotency

    def authorize(self, command: CommercialActionCommand) -> None:
        if not command.actor.actor_id:
            raise AuthorizationError("actor is required")

    def execute(self, command: CommercialActionCommand) -> str:
        self.authorize(command)
        decision = self._policy.evaluate(
            PolicyContext(
                actor_id=command.actor.actor_id,
                action="commercial_action",
                resource_type="identity",
                resource_id=command.identity_id,
                trusted_level=command.actor.trusted_level,
                evidence_level=command.evidence_level,
            )
        )
        if decision.decision is not Decision.ALLOW:
            raise PolicyDenied(decision.reason)

        existing = self._idempotency.get(command.command_id)
        if existing is not None:
            if existing.request_hash != command.request_hash:
                raise ValueError("idempotency key reused with different request")
            return existing.result_ref

        self._idempotency.reserve(
            key=command.command_id,
            request_hash=command.request_hash,
            result_ref=command.identity_id,
        )
        return command.identity_id

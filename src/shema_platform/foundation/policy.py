from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .errors import PolicyDenied


class Decision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class PolicyContext:
    actor_id: str
    action: str
    resource_type: str
    resource_id: str | None = None
    actor_trust_level: int = 0
    resource_trust_level: int = 0
    evidence_level: int = 0


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    decision: Decision
    reason: str


class PolicyEngine:
    """Small deterministic policy boundary; replaceable without changing domain code."""

    def evaluate(self, context: PolicyContext) -> PolicyDecision:
        if not context.actor_id:
            raise PolicyDenied("actor_id is required")

        if context.action in {"commercial_action", "order_create"}:
            if context.actor_trust_level < 2:
                return PolicyDecision(Decision.DENY, "actor_not_trusted")
            if context.resource_trust_level < 2:
                return PolicyDecision(Decision.DENY, "resource_not_verified")
            if context.evidence_level < 2:
                return PolicyDecision(Decision.REVIEW, "critical_claims_need_evidence")

        return PolicyDecision(Decision.ALLOW, "policy_ok")

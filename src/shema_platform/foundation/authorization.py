from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .errors import AuthorizationError


class Permission(StrEnum):
    COMMERCIAL_ACTION_CREATE = "commercial_action.create"
    COMMERCIAL_ACTION_SEND = "commercial_action.send"
    ORDER_CREATE = "order.create"
    ORDER_READ = "order.read"
    ECONOMICS_READ = "economics.read"
    DIAGNOSTICS_READ = "diagnostics.read"
    SEARCH_RUN = "search.run"
    DISCOVERY_RUN = "discovery.run"
    RESEARCH_RUN = "research.run"
    COUNTERPARTY_CHECK = "counterparty.check"
    INTELLIGENCE_RUN = "intelligence.run"
    INTELLIGENCE_PROVIDER_ACTIVATE = "intelligence.provider.activate"
    INTELLIGENCE_PROVIDER_LOOKUP = "intelligence.provider.lookup"
    INTELLIGENCE_PROVIDER_ROLLBACK = "intelligence.provider.rollback"
    AI_RUN = "ai.run"
    PUBLIC_INTAKE_REVIEW = "public_intake.review"


@dataclass(frozen=True, slots=True)
class AuthorizationSubject:
    actor_id: str
    permissions: frozenset[Permission]

    @classmethod
    def from_actor(
        cls,
        actor_id: str,
        permissions: frozenset[Permission],
    ) -> AuthorizationSubject:
        if not actor_id.strip():
            raise ValueError("actor_id is required")
        return cls(actor_id=actor_id, permissions=permissions)


class RBACAuthorizer:
    """Small explicit RBAC boundary; extensible toward ABAC/ReBAC later."""

    def __init__(self, subjects: tuple[AuthorizationSubject, ...] = ()) -> None:
        self._subjects = {subject.actor_id: subject for subject in subjects}

    def is_allowed(self, actor_id: str, permission: Permission) -> bool:
        subject = self._subjects.get(actor_id)
        return subject is not None and permission in subject.permissions

    def require(self, actor_id: str, permission: Permission) -> None:
        if not self.is_allowed(actor_id, permission):
            raise AuthorizationError(
                f"permission denied: actor={actor_id} permission={permission.value}"
            )

    def grant(self, actor_id: str, permissions: frozenset[Permission]) -> None:
        if not actor_id:
            raise ValueError("actor_id is required")
        self._subjects[actor_id] = AuthorizationSubject(
            actor_id=actor_id,
            permissions=permissions,
        )

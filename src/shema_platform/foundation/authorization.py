from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from .authentication import AuthenticatedActor
from .errors import AuthorizationError


class Permission(StrEnum):
    COMMERCIAL_ACTION_CREATE = "commercial_action.create"
    COMMERCIAL_ACTION_SEND = "commercial_action.send"
    ORDER_CREATE = "order.create"
    INTELLIGENCE_RUN = "intelligence.run"
    AI_RUN = "ai.run"


@dataclass(frozen=True, slots=True)
class AuthorizationSubject:
    actor_id: str
    permissions: frozenset[Permission]


@dataclass(frozen=True, slots=True)
class AuthorizationMaterializer:
    """Materializes explicit permissions from verified IAM roles/scopes."""

    role_permissions: Mapping[str, frozenset[Permission]]
    scope_permissions: Mapping[str, frozenset[Permission]]

    def materialize(self, actor: AuthenticatedActor) -> AuthorizationSubject:
        permissions: set[Permission] = set()
        for role in actor.roles:
            permissions.update(self.role_permissions.get(role, frozenset()))
        for scope in actor.scopes:
            permissions.update(self.scope_permissions.get(scope, frozenset()))
        return AuthorizationSubject(
            actor_id=actor.actor_id,
            permissions=frozenset(permissions),
        )


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

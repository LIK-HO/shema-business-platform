from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .authorization import Permission


class AuthenticationRequired(Exception):
    """The request did not carry a valid authenticated principal."""


@dataclass(frozen=True, slots=True)
class AuthenticatedActor:
    actor_id: str
    trust_level: int
    permissions: frozenset[Permission] = frozenset()

    def __post_init__(self) -> None:
        if not self.actor_id.strip():
            raise ValueError("actor_id is required")
        if self.trust_level < 0:
            raise ValueError("trust_level cannot be negative")


class AuthenticationPort(Protocol):
    """External IAM boundary. Token verification is an adapter concern."""

    def authenticate(self, authorization: str | None) -> AuthenticatedActor: ...

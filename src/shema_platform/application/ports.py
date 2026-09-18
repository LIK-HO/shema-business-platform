from __future__ import annotations

from typing import Protocol

from shema_platform.domain.identity import Identity
from shema_platform.domain.search import SearchHit


class IdentityRepository(Protocol):
    """Persistence port for canonical identities."""

    def find_by_tax_id(self, tax_id: str) -> Identity | None: ...

    def add(self, identity: Identity) -> None: ...


class SearchCandidateRepository(Protocol):
    """Persistence port for source-side discovery observations."""

    def add(self, candidate: SearchHit) -> None: ...


class QuarantineRepository(Protocol):
    """Persistence port for uncertain/conflicting records."""

    def add(
        self,
        *,
        object_type: str,
        object_ref: str,
        reason_code: str,
        payload: dict[str, object],
    ) -> None: ...

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from shema_platform.domain.identity import Identity, Resolution
from shema_platform.foundation.errors import IntegrityViolation


class IdentityMatch(StrEnum):
    NEW = "new"
    EXISTING = "existing"
    CONFLICT = "conflict"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class IdentityResolution:
    match: IdentityMatch
    resolution: Resolution
    existing_identity_ids: tuple[str, ...] = ()


class IdentityDirectory:
    """Single global identity index spanning all lifecycle states.

    Lifecycle state is data, not a separate deduplication namespace. This prevents
    the historic 'three lists' problem where the same organization could coexist
    independently in pool, clients, and verified views.
    """

    def __init__(self, identities: tuple[Identity, ...] = ()) -> None:
        self._identities = {identity.identity_id: identity for identity in identities}

    def all(self) -> tuple[Identity, ...]:
        return tuple(self._identities.values())

    def find_by_tax_id(self, tax_id: str) -> tuple[Identity, ...]:
        if not tax_id:
            return ()
        return tuple(identity for identity in self._identities.values() if identity.tax_id == tax_id)

    def resolve(self, candidate: Identity) -> IdentityResolution:
        if not candidate.tax_id:
            return IdentityResolution(
                match=IdentityMatch.REVIEW,
                resolution=Resolution.QUARANTINE,
            )

        matches = self.find_by_tax_id(candidate.tax_id)
        if not matches:
            return IdentityResolution(
                match=IdentityMatch.NEW,
                resolution=Resolution.KEEP_SEPARATE,
            )

        distinct_ids = tuple(identity.identity_id for identity in matches)
        if len(distinct_ids) > 1:
            raise IntegrityViolation(
                f"tax_id {candidate.tax_id} is already assigned to multiple identities"
            )

        existing = matches[0]
        if existing.identity_id == candidate.identity_id:
            return IdentityResolution(
                match=IdentityMatch.EXISTING,
                resolution=Resolution.MATCH,
                existing_identity_ids=distinct_ids,
            )

        return IdentityResolution(
            match=IdentityMatch.EXISTING,
            resolution=existing.resolve_with(candidate),
            existing_identity_ids=distinct_ids,
        )

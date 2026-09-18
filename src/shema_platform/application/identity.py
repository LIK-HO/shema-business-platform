from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from shema_platform.domain.identity import Identity, IdentityState, Resolution
from shema_platform.foundation.errors import IntegrityViolation, QuarantineRequired
from shema_platform.foundation.ids import Id


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
    """Single global identity index spanning every lifecycle state.

    External candidates are not canonical identities. A canonical identity_id is
    created only when the candidate passes identity resolution and registration rules.
    """

    def __init__(self, identities: tuple[Identity, ...] = ()) -> None:
        self._identities = {identity.identity_id: identity for identity in identities}

    def all(self) -> tuple[Identity, ...]:
        return tuple(self._identities.values())

    def find_by_tax_id(self, tax_id: str) -> tuple[Identity, ...]:
        normalized_tax_id = tax_id.strip()
        if not normalized_tax_id:
            return ()
        return tuple(
            identity
            for identity in self._identities.values()
            if identity.tax_id == normalized_tax_id
        )

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

    def register(self, candidate: Identity) -> Identity:
        if not candidate.tax_id:
            raise QuarantineRequired(
                "canonical identity registration requires tax_id"
            )
        if candidate.identity_id in self._identities:
            raise IntegrityViolation("identity_id is already registered")

        existing = self.find_by_tax_id(candidate.tax_id)
        if existing:
            raise IntegrityViolation("tax_id is already registered")

        self._identities[candidate.identity_id] = candidate
        return candidate

    def register_new(
        self,
        *,
        canonical_name: str,
        tax_id: str,
        registration_id: str | None = None,
    ) -> Identity:
        candidate = Identity(
            identity_id=str(Id.new()),
            canonical_name=canonical_name.strip(),
            state=IdentityState.IDENTIFIED,
            tax_id=tax_id.strip(),
            registration_id=registration_id.strip() if registration_id else None,
        )
        if not candidate.canonical_name:
            raise ValueError("canonical_name is required")
        return self.register(candidate)

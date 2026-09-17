from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from shema_platform.foundation.errors import QuarantineRequired


class IdentityState(StrEnum):
    RAW = "raw"
    CANDIDATE = "candidate"
    IDENTIFIED = "identified"
    VERIFIED = "verified"
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNKNOWN = "unknown"


class Resolution(StrEnum):
    MATCH = "match"
    MERGE = "merge"
    KEEP_SEPARATE = "keep_separate"
    QUARANTINE = "quarantine"
    MANUAL_REVIEW = "manual_review"


@dataclass(frozen=True, slots=True)
class Identity:
    identity_id: str
    canonical_name: str
    state: IdentityState
    tax_id: str | None = None
    registration_id: str | None = None

    def require_verified(self) -> None:
        if self.state not in {IdentityState.VERIFIED, IdentityState.ACTIVE}:
            raise QuarantineRequired("critical action requires verified identity")

    def can_merge(self, other: "Identity") -> bool:
        return bool(self.tax_id and other.tax_id and self.tax_id == other.tax_id)

    def resolve_with(self, other: "Identity") -> Resolution:
        if self.identity_id == other.identity_id:
            return Resolution.MATCH
        if self.can_merge(other):
            return Resolution.MERGE
        if not self.tax_id or not other.tax_id:
            return Resolution.QUARANTINE
        return Resolution.MANUAL_REVIEW

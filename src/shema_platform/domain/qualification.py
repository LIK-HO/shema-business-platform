from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class QualificationStatus(StrEnum):
    QUALIFIED = "qualified"
    REVIEW = "review"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class QualificationInput:
    identity_verified: bool
    contact_available: bool
    service_fit: bool
    evidence_level: int
    economic_fit: bool


@dataclass(frozen=True, slots=True)
class QualificationDecision:
    status: QualificationStatus
    reasons: tuple[str, ...]


class QualificationService:
    """Conservative qualification gate: uncertainty becomes review, not silent promotion."""

    def evaluate(self, value: QualificationInput) -> QualificationDecision:
        reasons: list[str] = []

        if not value.identity_verified:
            reasons.append("identity_not_verified")
        if value.evidence_level < 2:
            reasons.append("insufficient_evidence")

        if not value.identity_verified or value.evidence_level < 2:
            return QualificationDecision(QualificationStatus.REVIEW, tuple(reasons))

        if not value.contact_available:
            reasons.append("contact_unavailable")
        if not value.service_fit:
            reasons.append("service_mismatch")
        if not value.economic_fit:
            reasons.append("economic_fit_not_confirmed")

        if value.contact_available and value.service_fit and value.economic_fit:
            return QualificationDecision(QualificationStatus.QUALIFIED, ())

        return QualificationDecision(QualificationStatus.REVIEW, tuple(reasons))

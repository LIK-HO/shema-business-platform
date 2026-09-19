from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType


class TruthClass(StrEnum):
    FACT = "fact"
    EVIDENCE = "evidence"
    SIGNAL = "signal"
    HYPOTHESIS = "hypothesis"


class TrustLevel(StrEnum):
    T0_RAW = "T0"
    T1_OBSERVED = "T1"
    T2_VERIFIED = "T2"
    T3_DERIVED = "T3"
    T4_DECISION = "T4"


class EvidenceLifecycle(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"
    QUARANTINED = "quarantined"


@dataclass(frozen=True, slots=True)
class Evidence:
    evidence_id: str
    subject_ref: str
    claim: str
    source_ref: str
    observed_at: datetime
    captured_at: datetime
    truth_class: TruthClass
    trust_level: TrustLevel
    confidence: float
    provenance: Mapping[str, str] = field(default_factory=dict)
    expires_at: datetime | None = None
    lifecycle: EvidenceLifecycle = EvidenceLifecycle.ACTIVE

    def __post_init__(self) -> None:
        if not self.evidence_id.strip() or not self.subject_ref.strip():
            raise ValueError("evidence_id and subject_ref are required")
        if not self.claim.strip():
            raise ValueError("claim must not be empty")
        if not self.source_ref.strip():
            raise ValueError("source_ref must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.captured_at < self.observed_at:
            raise ValueError("captured_at cannot precede observed_at")
        if self.expires_at is not None and self.expires_at < self.observed_at:
            raise ValueError("expires_at cannot precede observed_at")

        normalized_provenance = {
            key.strip(): value.strip()
            for key, value in self.provenance.items()
            if key.strip() and value.strip()
        }
        object.__setattr__(
            self,
            "provenance",
            MappingProxyType(normalized_provenance),
        )

    def is_current(self, at: datetime) -> bool:
        if self.lifecycle is not EvidenceLifecycle.ACTIVE:
            return False
        return self.expires_at is None or at <= self.expires_at

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


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

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if not self.claim.strip():
            raise ValueError("claim must not be empty")
        if not self.source_ref.strip():
            raise ValueError("source_ref must not be empty")

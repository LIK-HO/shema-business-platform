from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite


class BenchmarkResolution(StrEnum):
    MATCH = "match"
    KEEP_SEPARATE = "keep_separate"
    MANUAL_REVIEW = "manual_review"
    QUARANTINE = "quarantine"


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    case_id: str
    expected_resolution: BenchmarkResolution
    requires_provenance: bool = True
    requires_freshness: bool = True

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case_id is required")


@dataclass(frozen=True, slots=True)
class ResolutionMetrics:
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int

    def __post_init__(self) -> None:
        if min(
            self.true_positive,
            self.false_positive,
            self.true_negative,
            self.false_negative,
        ) < 0:
            raise ValueError("metric counts cannot be negative")

    @property
    def precision(self) -> float:
        denominator = self.true_positive + self.false_positive
        return self.true_positive / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        denominator = self.true_positive + self.false_negative
        return self.true_positive / denominator if denominator else 0.0

    @property
    def false_positive_rate(self) -> float:
        denominator = self.false_positive + self.true_negative
        return self.false_positive / denominator if denominator else 0.0

    @property
    def false_negative_rate(self) -> float:
        denominator = self.false_negative + self.true_positive
        return self.false_negative / denominator if denominator else 0.0

    def as_dict(self) -> dict[str, float | int]:
        return {
            "true_positive": self.true_positive,
            "false_positive": self.false_positive,
            "true_negative": self.true_negative,
            "false_negative": self.false_negative,
            "precision": self.precision,
            "recall": self.recall,
            "false_positive_rate": self.false_positive_rate,
            "false_negative_rate": self.false_negative_rate,
        }


@dataclass(frozen=True, slots=True)
class QualityMetrics:
    provenance_complete: int
    provenance_total: int
    freshness_correct: int
    freshness_total: int
    operator_corrections: int
    operator_decisions: int

    def __post_init__(self) -> None:
        if min(
            self.provenance_complete,
            self.provenance_total,
            self.freshness_correct,
            self.freshness_total,
            self.operator_corrections,
            self.operator_decisions,
        ) < 0:
            raise ValueError("quality counts cannot be negative")
        if self.provenance_complete > self.provenance_total:
            raise ValueError("provenance_complete cannot exceed provenance_total")
        if self.freshness_correct > self.freshness_total:
            raise ValueError("freshness_correct cannot exceed freshness_total")
        if self.operator_corrections > self.operator_decisions:
            raise ValueError("operator_corrections cannot exceed operator_decisions")

    @property
    def provenance_completeness(self) -> float:
        return (
            self.provenance_complete / self.provenance_total
            if self.provenance_total
            else 0.0
        )

    @property
    def freshness_correctness(self) -> float:
        return self.freshness_correct / self.freshness_total if self.freshness_total else 0.0

    @property
    def operator_correction_rate(self) -> float:
        return (
            self.operator_corrections / self.operator_decisions
            if self.operator_decisions
            else 0.0
        )

    def as_dict(self) -> dict[str, float | int]:
        return {
            "provenance_completeness": self.provenance_completeness,
            "freshness_correctness": self.freshness_correctness,
            "operator_correction_rate": self.operator_correction_rate,
        }


def evaluate_resolution(
    *,
    all_case_ids: set[str],
    expected_matches: set[str],
    actual_matches: set[str],
) -> ResolutionMetrics:
    if not expected_matches.issubset(all_case_ids):
        raise ValueError("expected_matches contains unknown case ids")
    if not actual_matches.issubset(all_case_ids):
        raise ValueError("actual_matches contains unknown case ids")

    true_positive = len(expected_matches & actual_matches)
    false_positive = len(actual_matches - expected_matches)
    false_negative = len(expected_matches - actual_matches)
    true_negative = len(all_case_ids - expected_matches - actual_matches)

    return ResolutionMetrics(
        true_positive=true_positive,
        false_positive=false_positive,
        true_negative=true_negative,
        false_negative=false_negative,
    )


def validate_metric_value(value: float) -> float:
    if not isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError("metric value must be finite and within [0, 1]")
    return value

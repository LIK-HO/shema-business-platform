from __future__ import annotations

import json
from pathlib import Path

import pytest

from shema_platform.application.intelligence_benchmark import (
    BenchmarkCase,
    BenchmarkResolution,
    QualityMetrics,
    evaluate_resolution,
    validate_metric_value,
)

ROOT = Path(__file__).parents[1]


def load_json(name: str) -> dict:
    return json.loads(
        (ROOT / "architecture" / name).read_text(encoding="utf-8")
    )


def test_source_registry_is_declarative_and_network_disabled() -> None:
    contract = load_json("intelligence_source_registry_contract.json")

    assert contract["version"] == "1.0"
    assert contract["policy"]["no_new_kernel_semantics"] is True
    assert contract["policy"]["network_execution_enabled"] is False
    assert contract["policy"]["source_reliability_separate_from_claim_confidence"] is True

    sources = contract["sources"]
    assert len(sources) >= 6
    assert len({item["source_id"] for item in sources}) == len(sources)
    assert all(item["network_automation"] is False for item in sources)
    assert {
        item["source_class"] for item in sources
    } == {
        "official_registry",
        "primary_company",
        "authoritative_public_record",
        "trusted_structured_dataset",
        "open_web_signal",
    }


def test_benchmark_corpus_is_permanent_synthetic_and_complete() -> None:
    contract = load_json("intelligence_benchmark_contract.json")

    assert contract["status"] == "permanent_synthetic_baseline"
    assert contract["policy"]["synthetic_data_only"] is True
    assert contract["policy"]["no_personal_data"] is True
    assert contract["policy"]["no_live_source_lookup"] is True

    cases = contract["cases"]
    assert len(cases) == 10
    assert len({item["case_id"] for item in cases}) == 10
    assert {
        item["class"] for item in cases
    } >= {
        "exact_identifier_match",
        "same_name_different_entity",
        "old_identifier",
        "changed_registration",
        "duplicate_sources",
        "contradictory_claims",
        "stale_claim",
        "missing_identifier",
        "misleading_near_match",
    }


def test_benchmark_resolution_metrics_are_bounded() -> None:
    all_cases = {f"B{i:02d}" for i in range(1, 11)}
    expected = {"B01", "B03", "B05"}
    actual = {"B01", "B05", "B09"}

    metrics = evaluate_resolution(
        all_case_ids=all_cases,
        expected_matches=expected,
        actual_matches=actual,
    )

    assert metrics.true_positive == 2
    assert metrics.false_positive == 1
    assert metrics.false_negative == 1
    assert metrics.true_negative == 6
    assert metrics.precision == pytest.approx(2 / 3)
    assert metrics.recall == pytest.approx(2 / 3)
    assert metrics.false_positive_rate == pytest.approx(1 / 7)
    assert metrics.false_negative_rate == pytest.approx(1 / 3)
    assert all(
        0.0 <= value <= 1.0
        for value in (
            metrics.precision,
            metrics.recall,
            metrics.false_positive_rate,
            metrics.false_negative_rate,
        )
    )


def test_resolution_rejects_unknown_case_ids() -> None:
    with pytest.raises(ValueError, match="unknown case ids"):
        evaluate_resolution(
            all_case_ids={"B01"},
            expected_matches={"B99"},
            actual_matches=set(),
        )

    with pytest.raises(ValueError, match="unknown case ids"):
        evaluate_resolution(
            all_case_ids={"B01"},
            expected_matches=set(),
            actual_matches={"B99"},
        )


def test_benchmark_case_requires_an_id() -> None:
    with pytest.raises(ValueError, match="case_id"):
        BenchmarkCase("", BenchmarkResolution.MATCH)


def test_quality_metrics_reject_inconsistent_counts() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        QualityMetrics(
            provenance_complete=2,
            provenance_total=1,
            freshness_correct=1,
            freshness_total=1,
            operator_corrections=0,
            operator_decisions=1,
        )

    with pytest.raises(ValueError, match="cannot exceed"):
        QualityMetrics(
            provenance_complete=1,
            provenance_total=1,
            freshness_correct=2,
            freshness_total=1,
            operator_corrections=0,
            operator_decisions=1,
        )

    with pytest.raises(ValueError, match="cannot exceed"):
        QualityMetrics(
            provenance_complete=1,
            provenance_total=1,
            freshness_correct=1,
            freshness_total=1,
            operator_corrections=2,
            operator_decisions=1,
        )


def test_quality_metrics_expose_separate_dimensions() -> None:
    metrics = QualityMetrics(
        provenance_complete=8,
        provenance_total=10,
        freshness_correct=9,
        freshness_total=10,
        operator_corrections=1,
        operator_decisions=5,
    )

    assert metrics.provenance_completeness == pytest.approx(0.8)
    assert metrics.freshness_correctness == pytest.approx(0.9)
    assert metrics.operator_correction_rate == pytest.approx(0.2)
    assert set(metrics.as_dict()) == {
        "provenance_completeness",
        "freshness_correctness",
        "operator_correction_rate",
    }


@pytest.mark.parametrize("value", [-0.01, 1.01, float("inf"), float("nan")])
def test_metric_value_validation_is_fail_closed(value: float) -> None:
    with pytest.raises(ValueError, match="metric value"):
        validate_metric_value(value)

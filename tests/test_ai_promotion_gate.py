from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from shema_platform.platform import ai_promotion_gate


ROOT = Path(__file__).resolve().parents[1]


def test_ai_promotion_assessment_is_green_without_activation() -> None:
    assessment = ai_promotion_gate.assess_ai_promotion(ROOT)

    assert assessment.promotable is True
    assert assessment.kernel_contract_version == "1.4"
    assert assessment.core_maturity_contract_version == "1.5-core-maturity"
    assert assessment.frozen_ai_kernel_integrity is True
    assert assessment.approved_providers == ("yandexgpt", "gigachat")
    assert assessment.automatic_fallback is False
    assert assessment.automatic_activation is False
    assert assessment.live_traffic_in_evidence is False
    assert assessment.runtime_secret_handling_verified is True
    assert assessment.release_contract_validated is True
    assert "scripts/postgres_pitr_drill.sh" in assessment.evidence_refs
    assert ".github/workflows/ci.yml" in assessment.evidence_refs


def test_operator_approval_is_explicit_and_does_not_activate_provider() -> None:
    assessment = ai_promotion_gate.assess_ai_promotion(ROOT)

    approval = ai_promotion_gate.approve_ai_promotion(
        assessment,
        approved_by="operator-1",
        reason="P39 release checkpoint accepted for the reviewed source tree",
        approved_at=datetime(2026, 9, 25, 12, 0, tzinfo=UTC),
    )

    assert approval.approved_by == "operator-1"
    assert approval.assessment_kernel_contract_version == "1.4"
    assert approval.assessment_evidence_refs == assessment.evidence_refs


def test_approval_fails_closed_for_non_promotable_assessment() -> None:
    assessment = ai_promotion_gate.assess_ai_promotion(ROOT)
    blocked = replace(assessment, automatic_activation=True)

    with pytest.raises(
        ai_promotion_gate.AIPromotionGateError,
        match="not promotable",
    ):
        ai_promotion_gate.approve_ai_promotion(
            blocked,
            approved_by="operator-1",
            reason="must fail",
        )


def test_frozen_ai_kernel_integrity_fails_closed(monkeypatch) -> None:
    monkeypatch.setitem(
        ai_promotion_gate.assess_ai_promotion.__globals__,
        "FROZEN_AI_KERNEL_GIT_BLOB_SHA",
        "0000000000000000000000000000000000000000",
    )

    with pytest.raises(
        ai_promotion_gate.AIPromotionGateError,
        match="frozen AI kernel integrity mismatch",
    ):
        ai_promotion_gate.assess_ai_promotion(ROOT)


def test_promotion_gate_contract_has_no_activation_or_credential_path() -> None:
    source = (
        ROOT / "src" / "shema_platform" / "platform" / "ai_promotion_gate.py"
    ).read_text(encoding="utf-8")

    assert "activate_yandexgpt" not in source
    assert "activate_gigachat" not in source
    assert "authorization_key=" not in source
    assert "api_key=" not in source
    assert "GIGACHAT_AUTHORIZATION_KEY" not in source

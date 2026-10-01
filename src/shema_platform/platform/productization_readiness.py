from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class ProductizationReadinessError(RuntimeError):
    """The v1.5 readiness assessment cannot be computed safely."""


@dataclass(frozen=True, slots=True)
class ReadinessCheck:
    key: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class ProductizationReadinessReport:
    status: str
    checks: tuple[ReadinessCheck, ...]
    blockers: tuple[str, ...]
    scope_safe: bool

    @property
    def production_ready(self) -> bool:
        return self.status == "ready" and not self.blockers and self.scope_safe


def _read_json(root: Path, relative_path: str) -> dict[str, object]:
    path = root / relative_path
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductizationReadinessError(
            f"invalid readiness evidence: {relative_path}"
        ) from exc


def _check(
    checks: list[ReadinessCheck],
    key: str,
    condition: bool,
    detail: str,
) -> None:
    checks.append(ReadinessCheck(key=key, passed=condition, detail=detail))


def assess_v15_productization_readiness(root: Path) -> ProductizationReadinessReport:
    root = root.resolve()

    required = {
        "kernel": "architecture/contract.json",
        "maturity": "architecture/core_maturity_contract.json",
        "release": "architecture/release_candidate_contract.json",
        "ai_promotion": "architecture/ai_promotion_release_gate_contract.json",
        "ai_rehearsal": "architecture/ai_production_rehearsal_contract.json",
        "max_idempotency": "architecture/max_reconciliation_idempotency_contract.json",
        "max_provider": "architecture/max_provider_evidence_contract.json",
        "max_ambiguous": "architecture/max_ambiguous_outcome_safety_contract.json",
        "quarantine_read": "architecture/quarantine_read_model_contract.json",
    }

    evidence = {
        name: _read_json(root, relative_path)
        for name, relative_path in required.items()
    }

    checks: list[ReadinessCheck] = []
    blockers: list[str] = []

    kernel_ok = (
        evidence["kernel"].get("version") == "1.4"
        and evidence["maturity"].get("version") == "1.5-core-maturity"
        and evidence["maturity"].get("core_semantic_freeze_after_certification") is True
    )
    _check(
        checks,
        "frozen_kernel",
        kernel_ok,
        "v1.4 kernel contract + v1.5 core semantic freeze",
    )
    if not kernel_ok:
        blockers.append("frozen kernel / core maturity contract mismatch")

    release_ok = evidence["release"].get("release_version") == "1.5.0"
    _check(
        checks,
        "release_contract_baseline",
        release_ok,
        "release candidate contract remains 1.5.0",
    )
    if not release_ok:
        blockers.append("release candidate contract mismatch")

    ai_allowlist_ok = (
        evidence["ai_promotion"]["approved_provider_policy"]["allow_list"]
        == ["yandexgpt", "gigachat"]
    )
    ai_fallback_ok = (
        evidence["ai_promotion"]["approved_provider_policy"]["automatic_fallback"]
        is False
    )
    ai_activation_ok = (
        evidence["ai_promotion"]["approved_provider_policy"]["automatic_activation"]
        is False
    )
    ai_ok = ai_allowlist_ok and ai_fallback_ok and ai_activation_ok
    _check(
        checks,
        "ai_promotion",
        ai_ok,
        "approved providers only; no automatic fallback or activation",
    )
    if not ai_ok:
        blockers.append("AI promotion policy is not fail-closed")

    rehearsal_ok = (
        evidence["ai_rehearsal"]["activation"]["explicit_operator_required"] is True
        and evidence["ai_rehearsal"]["activation"]["activation_makes_no_external_call"]
        is True
        and evidence["ai_rehearsal"]["rollback"]["restores_disabled_state"] is True
    )
    _check(
        checks,
        "ai_activation_rehearsal",
        rehearsal_ok,
        "explicit activation + no-network rehearsal + rollback",
    )
    if not rehearsal_ok:
        blockers.append("AI activation rehearsal is incomplete")

    max_platform_ok = (
        evidence["max_idempotency"]["proof"]["same_request_replay_returns_same_external_identity"]
        is True
        and evidence["max_idempotency"]["proof"]["same_key_different_payload_fails_closed"]
        is True
        and evidence["max_idempotency"]["proof"]["unsafe_provider_capability_fails_closed"]
        is True
    )
    _check(
        checks,
        "max_platform_effect_safety",
        max_platform_ok,
        "platform-side deterministic idempotency/quarantine safety is proven",
    )
    if not max_platform_ok:
        blockers.append("MAX platform-side external-effect safety is incomplete")

    max_provider_idempotency = (
        evidence["max_provider"]["external_effect_safety"][
            "provider_side_idempotency_contract_documented"
        ]
        is True
    )
    _check(
        checks,
        "max_provider_idempotency",
        max_provider_idempotency,
        "provider-side idempotent send contract",
    )
    if not max_provider_idempotency:
        blockers.append(
            "MAX provider-side idempotency contract is not documented/certified"
        )

    max_provider_reconciliation = (
        evidence["max_provider"]["external_effect_safety"][
            "provider_side_reconciliation_contract_documented"
        ]
        is True
    )
    _check(
        checks,
        "max_provider_reconciliation",
        max_provider_reconciliation,
        "provider-side reconciliation contract",
    )
    if not max_provider_reconciliation:
        blockers.append(
            "MAX provider-side reconciliation contract is not documented/certified"
        )

    max_ambiguous_ok = (
        evidence["max_ambiguous"]["handling"]["automatic_external_replay"] is False
        and evidence["max_ambiguous"]["replay_proof"][
            "same_command_after_quarantine_reaches_adapter"
        ]
        is False
    )
    _check(
        checks,
        "max_ambiguous_fail_closed",
        max_ambiguous_ok,
        "ambiguous MAX outcomes become durable FAILED/quarantine with no replay",
    )
    if not max_ambiguous_ok:
        blockers.append("MAX ambiguous-outcome fail-closed path is incomplete")

    quarantine_read_ok = (
        evidence["quarantine_read"]["storage"]["read_only"] is True
        and evidence["quarantine_read"]["state_change"]["failed_to_sent_transition"]
        is False
        and evidence["quarantine_read"]["state_change"]["external_send"] is False
    )
    _check(
        checks,
        "quarantine_read_model",
        quarantine_read_ok,
        "quarantine inspection is read-only and cannot send or resolve state",
    )
    if not quarantine_read_ok:
        blockers.append("quarantine read model is not strictly read-only")

    scope_safe = all(
        evidence[name].get("frozen_kernel_impact", False) is False
        for name in (
            "ai_promotion",
            "ai_rehearsal",
            "max_idempotency",
            "max_provider",
            "max_ambiguous",
            "quarantine_read",
        )
        if name in evidence
    )
    _check(
        checks,
        "scope_safety",
        scope_safe,
        "all audited productization layers declare no frozen-kernel impact",
    )
    if not scope_safe:
        blockers.append("one or more productization contracts report frozen-kernel impact")

    status = "ready" if not blockers else "blocked"
    return ProductizationReadinessReport(
        status=status,
        checks=tuple(checks),
        blockers=tuple(blockers),
        scope_safe=scope_safe,
    )

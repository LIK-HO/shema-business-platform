# ruff: noqa: I001

from __future__ import annotations

import json
from pathlib import Path

from shema_platform.application.search_adapter_readiness import (
    ActivationReadiness,
    SearchAdapterReadinessEvidence,
    SearchAdapterReadinessGate,
)


ROOT = Path(__file__).parents[1]


def baseline(**overrides) -> SearchAdapterReadinessEvidence:
    values = {
        "registry_source": True,
        "authoritative_provider_contract": True,
        "lawful_access_evidence": True,
        "adapter_descriptor": True,
        "rate_limit_evidence": True,
        "timeout_policy": True,
        "error_mapping": True,
        "provenance_mapping": True,
        "kill_switch": True,
        "rollback_plan": True,
        "deterministic_fixture_tests": True,
        "observability_contract": True,
        "provider_is_selected": True,
        "activation_authorized": False,
    }
    values.update(overrides)
    return SearchAdapterReadinessEvidence(**values)


def test_contract_disallows_live_execution_and_automatic_activation() -> None:
    payload = json.loads(
        (
            ROOT / "architecture" / "search_adapter_activation_readiness_contract.json"
        ).read_text(encoding="utf-8")
    )
    assert payload["network_execution_enabled"] is False
    assert payload["automatic_activation"] is False
    assert payload["automatic_retry"] is False
    assert payload["fallback_provider"] is False


def test_unselected_provider_is_not_ready() -> None:
    result = SearchAdapterReadinessGate().evaluate(
        baseline(provider_is_selected=False)
    )
    assert result.state is ActivationReadiness.NOT_READY
    assert result.missing_evidence == ("provider_selection",)


def test_missing_evidence_is_explicit() -> None:
    result = SearchAdapterReadinessGate().evaluate(
        baseline(
            lawful_access_evidence=False,
            provenance_mapping=False,
            kill_switch=False,
        )
    )
    assert result.state is ActivationReadiness.EVIDENCE_REQUIRED
    assert result.missing_evidence == (
        "lawful_access_evidence",
        "provenance_mapping",
        "kill_switch",
    )


def test_complete_evidence_requires_separate_authorization() -> None:
    result = SearchAdapterReadinessGate().evaluate(baseline())
    assert result.state is ActivationReadiness.READY_FOR_CONTROLLED_ACTIVATION
    assert result.missing_evidence == ("explicit_operator_authorization",)


def test_activation_authorization_does_not_perform_activation() -> None:
    result = SearchAdapterReadinessGate().evaluate(
        baseline(activation_authorized=True)
    )
    assert result.state is ActivationReadiness.BLOCKED
    assert result.missing_evidence == (
        "live_activation_is_a_separate_authorized_operation",
    )

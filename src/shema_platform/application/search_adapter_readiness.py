from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ActivationReadiness(StrEnum):
    NOT_READY = "NOT_READY"
    EVIDENCE_REQUIRED = "EVIDENCE_REQUIRED"
    READY_FOR_CONTROLLED_ACTIVATION = "READY_FOR_CONTROLLED_ACTIVATION"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class SearchAdapterReadinessEvidence:
    registry_source: bool
    authoritative_provider_contract: bool
    lawful_access_evidence: bool
    adapter_descriptor: bool
    rate_limit_evidence: bool
    timeout_policy: bool
    error_mapping: bool
    provenance_mapping: bool
    kill_switch: bool
    rollback_plan: bool
    deterministic_fixture_tests: bool
    observability_contract: bool
    provider_is_selected: bool = False
    activation_authorized: bool = False


@dataclass(frozen=True, slots=True)
class SearchAdapterReadinessResult:
    state: ActivationReadiness
    missing_evidence: tuple[str, ...]


class SearchAdapterReadinessGate:
    REQUIRED_FIELDS = (
        "registry_source",
        "authoritative_provider_contract",
        "lawful_access_evidence",
        "adapter_descriptor",
        "rate_limit_evidence",
        "timeout_policy",
        "error_mapping",
        "provenance_mapping",
        "kill_switch",
        "rollback_plan",
        "deterministic_fixture_tests",
        "observability_contract",
    )

    def evaluate(
        self,
        evidence: SearchAdapterReadinessEvidence,
    ) -> SearchAdapterReadinessResult:
        if not evidence.provider_is_selected:
            return SearchAdapterReadinessResult(
                state=ActivationReadiness.NOT_READY,
                missing_evidence=("provider_selection",),
            )

        missing = tuple(
            field
            for field in self.REQUIRED_FIELDS
            if not getattr(evidence, field)
        )
        if missing:
            return SearchAdapterReadinessResult(
                state=ActivationReadiness.EVIDENCE_REQUIRED,
                missing_evidence=missing,
            )

        if not evidence.activation_authorized:
            return SearchAdapterReadinessResult(
                state=ActivationReadiness.READY_FOR_CONTROLLED_ACTIVATION,
                missing_evidence=("explicit_operator_authorization",),
            )

        return SearchAdapterReadinessResult(
            state=ActivationReadiness.BLOCKED,
            missing_evidence=(
                "live_activation_is_a_separate_authorized_operation",
            ),
        )

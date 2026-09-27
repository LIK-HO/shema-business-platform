# ruff: noqa: I001

from __future__ import annotations

import json
from pathlib import Path

from shema_platform.application.search_adapter_readiness import (
    ActivationReadiness,
    SearchAdapterReadinessEvidence,
    SearchAdapterReadinessGate,
)
from shema_platform.application.search_planning import SearchSourceRegistry


ROOT = Path(__file__).parents[1]


def load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_selected_source_matches_registry_and_preserves_disabled_network() -> None:
    registry_contract = load_json(
        "architecture/intelligence_source_registry_contract.json"
    )
    source_contract = load_json(
        "architecture/fns_transparent_business_adapter_contract.json"
    )

    source = next(
        item
        for item in registry_contract["sources"]
        if item["source_id"] == source_contract["source_id"]
    )
    binding = source_contract["registry_binding"]

    assert source["source_id"] == "fns_transparent_business"
    assert binding["source_class"] == source["source_class"]
    assert binding["reliability"] == source["default_reliability"]
    assert binding["access_mode"] == source["access_mode"]
    assert binding["network_automation"] is False
    assert source_contract["adapter_boundary"]["network_execution_enabled"] is False


def test_selected_source_can_be_loaded_through_registry_contract() -> None:
    registry = SearchSourceRegistry.from_contract(
        load_json("architecture/intelligence_source_registry_contract.json")
    )
    source = registry.resolve(("fns_transparent_business",))[0]

    assert source.name == "FNS Transparent Business"
    assert source.source_class == "official_registry"
    assert source.reliability == "authoritative"
    assert source.access_mode == "manual_operator_lookup"


def test_authoritative_evidence_records_only_supported_provider_facts() -> None:
    evidence = load_json(
        "architecture/fns_transparent_business_evidence_2026_09_27.json"
    )

    urls = [item["url"] for item in evidence["authoritative_evidence"]]
    assert all(
        url.startswith("https://www.nalog.gov.ru/")
        or url == "https://pb.nalog.ru/od.html"
        for url in urls
    )

    facts = evidence["verified_provider_contract"]
    assert facts["public_service_exists"] is True
    assert facts["official_service_domain"] == "pb.nalog.ru"
    assert facts["manual_lookup_available"] is True
    assert facts["declared_availability"] == "24/7"
    assert facts["declared_data_refresh"] == "daily"

    for key, value in evidence["not_established"].items():
        assert value is True, key


def test_activation_remains_blocked_when_provider_automation_evidence_is_missing() -> None:
    contract = load_json(
        "architecture/fns_transparent_business_adapter_contract.json"
    )
    boundary = contract["adapter_boundary"]
    assert contract["activation_decision"] == "BLOCKED"
    assert boundary["network_execution_enabled"] is False
    assert contract["limits"]["provider_rate_limit"]["status"] == "NOT_ESTABLISHED"
    assert contract["limits"]["provider_timeout_contract"]["status"] == "NOT_ESTABLISHED"

    readiness = SearchAdapterReadinessGate().evaluate(
        SearchAdapterReadinessEvidence(
            registry_source=True,
            authoritative_provider_contract=True,
            lawful_access_evidence=True,
            adapter_descriptor=True,
            rate_limit_evidence=False,
            timeout_policy=False,
            error_mapping=False,
            provenance_mapping=True,
            kill_switch=True,
            rollback_plan=True,
            deterministic_fixture_tests=True,
            observability_contract=True,
            provider_is_selected=True,
            activation_authorized=False,
        )
    )

    assert readiness.state is ActivationReadiness.EVIDENCE_REQUIRED
    assert readiness.missing_evidence == (
        "rate_limit_evidence",
        "timeout_policy",
        "error_mapping",
    )


def test_contract_has_no_hidden_activation_or_fallback_path() -> None:
    contract = load_json(
        "architecture/fns_transparent_business_adapter_contract.json"
    )
    boundary = contract["adapter_boundary"]

    assert boundary["automatic_activation"] is False
    assert boundary["automatic_retry"] is False
    assert boundary["fallback_provider"] is False
    assert boundary["ranking_authority"] is False
    assert boundary["qualification_authority"] is False
    assert contract["kill_switch"]["activation_path_present"] is False

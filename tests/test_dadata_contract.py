from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


def dadata_contract() -> dict:
    return json.loads(
        (ROOT / "architecture" / "dadata_adapter_contract.json").read_text(
            encoding="utf-8"
        )
    )


def dadata_evidence() -> dict:
    return json.loads(
        (
            ROOT
            / "architecture"
            / "dadata_provider_evidence_2026_09_27.json"
        ).read_text(encoding="utf-8")
    )


def test_dadata_is_registered_as_trusted_secondary_and_not_authoritative() -> None:
    registry = json.loads(
        (
            ROOT
            / "architecture"
            / "intelligence_source_registry_contract.json"
        ).read_text(encoding="utf-8")
    )
    source = next(
        item
        for item in registry["sources"]
        if item["source_id"] == "dadata_organization_api"
    )
    assert source["source_class"] == "trusted_structured_dataset"
    assert source["default_reliability"] == "trusted_secondary"
    assert source["network_automation"] is False
    assert source["authority_rule"] == (
        "provider_output_is_evidence_input_not_canonical_truth"
    )


def test_dadata_provider_contract_has_documented_execution_facts() -> None:
    payload = dadata_contract()
    assert payload["endpoint"]["method"] == "POST"
    assert payload["endpoint"]["authorization"] == "Authorization: Token <API_KEY>"
    assert payload["provider_limits"]["requests_per_second_per_ip"] == 30
    assert payload["provider_limits"]["new_connections_per_minute_per_ip"] == 60
    assert payload["endpoint"]["query_max_length"] == 300
    assert payload["endpoint"]["count_max"] == 300
    assert payload["error_mapping"]["429"] == "PROVIDER_RATE_LIMIT"
    assert payload["error_mapping"]["5xx"] == "PROVIDER_INTERNAL_ERROR"


def test_dadata_explicitly_does_not_invent_undocumented_provider_semantics() -> None:
    payload = dadata_contract()
    assert payload["retry_policy"]["provider_retry_after_semantics"] == "NOT_ESTABLISHED"
    assert (
        payload["timeout_policy"]["provider_specific_timeout_contract"]
        == "NOT_DOCUMENTED"
    )


def test_dadata_activation_is_off_and_secret_is_never_repo_stored() -> None:
    payload = dadata_contract()
    assert payload["registry_binding"]["activation_off_by_default"] is True
    assert payload["credential_boundary"]["repository_storage"] is False
    assert payload["kill_switch"]["network_execution_enabled"] is False


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("400", "INVALID_REQUEST"),
        ("401", "MISSING_API_KEY"),
        ("403", "API_KEY_OR_ACCOUNT_NOT_AUTHORIZED_OR_DAILY_LIMIT"),
        ("405", "METHOD_NOT_ALLOWED"),
        ("413", "REQUEST_TOO_LARGE"),
        ("429", "PROVIDER_RATE_LIMIT"),
        ("5xx", "PROVIDER_INTERNAL_ERROR"),
    ],
)
def test_dadata_error_mapping_is_explicit(code: str, expected: str) -> None:
    assert dadata_contract()["error_mapping"][code] == expected


def test_dadata_evidence_does_not_upgrade_provider_to_canonical_authority() -> None:
    evidence = dadata_evidence()
    assert evidence["policy_interpretation"]["classification"] == "trusted_secondary"
    assert evidence["policy_interpretation"]["canonical_truth"] is False
    assert evidence["policy_interpretation"]["automatic_truth_promotion"] is False

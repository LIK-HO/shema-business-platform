import json
from pathlib import Path


BLOCKERS = {
    "MAX provider-side idempotency contract is not documented/certified",
    "MAX provider-side reconciliation contract is not documented/certified",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_contract() -> dict[str, object]:
    path = repo_root() / "architecture/max_provider_evidence_revalidation_contract.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_p46_revalidation_is_evidence_only_and_blocked() -> None:
    contract = read_contract()

    assert contract["version"] == "1.0"
    assert contract["status"] == "max_provider_external_effect_evidence_hold"
    assert contract["provider"]["id"] == "max"
    assert contract["provider"]["live_network_used"] is False
    assert contract["provider"]["credentials_used"] is False

    findings = contract["findings"]
    assert findings["send_method_documented"] is True
    assert findings["success_message_identity_documented"] is True
    assert findings["message_get_by_id_documented"] is True
    assert findings["per_destination_rate_limit_documented"] is True
    assert findings["idempotency_key_header_documented"] is False
    assert findings["client_supplied_idempotency_parameter_documented"] is False
    assert findings["provider_side_deduplication_semantics_documented"] is False
    assert findings["provider_side_reconciliation_by_client_operation_key_documented"] is False
    assert findings["reconciliation_by_known_message_id_available"] is True

    decision = contract["decision"]
    assert decision["provider_side_idempotency_verified"] is False
    assert decision["provider_side_reconciliation_verified"] is False
    assert decision["max_live_outbound_activation_allowed"] is False
    assert decision["automatic_live_retry_allowed"] is False
    assert decision["readiness_status_remains"] == "blocked"

    assert set(contract["blockers"]) == BLOCKERS


def test_p46_scope_stop_forbids_product_expansion() -> None:
    scope_stop = read_contract()["scope_stop"]

    assert scope_stop["no_provider_code_change"] is True
    assert scope_stop["no_new_execution_path"] is True
    assert scope_stop["no_database_migration"] is True
    assert scope_stop["no_frozen_kernel_semantic_change"] is True
    assert scope_stop["no_automatic_retry"] is True
    assert scope_stop["no_live_max_network"] is True
    assert scope_stop["no_production_activation"] is True
    assert scope_stop["no_compensating_provider"] is True
    assert scope_stop["no_cloud_local_fallback"] is True


def test_p46_source_set_is_authoritative_and_complete() -> None:
    sources = read_contract()["sources"]
    urls = {source["url"] for source in sources}

    assert "https://dev.max.ru/docs-api/methods/POST/messages" in urls
    assert "https://dev.max.ru/docs-api/methods/GET/messages" in urls
    assert "https://dev.max.ru/docs-api/methods/GET/messages/-messageId-" in urls
    assert "https://dev.max.ru/docs-api" in urls
    assert (
        "https://github.com/max-messenger-bot/max-bot-api-schemas/blob/main/"
        "schema_2026_07_01.json"
    ) in urls
    assert all(source["checked"] is True for source in sources)

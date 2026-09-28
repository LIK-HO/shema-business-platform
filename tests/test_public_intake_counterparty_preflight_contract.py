import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def load(name: str) -> dict:
    return json.loads((ROOT / "architecture" / name).read_text(encoding="utf-8"))


def test_public_intake_is_minimal_and_progressive() -> None:
    payload = load("public_intake_counterparty_preflight_contract.json")

    assert payload["public_form"]["minimum_fields"] == [
        "service_type",
        "location",
        "preferred_date_or_period",
        "work_or_cargo_description",
        "contact_name",
        "contact_channel",
    ]
    assert "inn" in payload["public_form"]["conditional_fields"]
    assert "ogrn_or_ogrnip" in payload["public_form"]["conditional_fields"]


def test_counterparty_preflight_is_deterministic_before_ai() -> None:
    payload = load("public_intake_counterparty_preflight_contract.json")

    policy = payload["counterparty_preflight"]["gpt_policy"]
    assert policy["used_for_initial_identifier_validation"] is False
    assert policy["used_for_registry_lookup"] is False
    assert policy["used_when_deterministic_evidence_is_sufficient"] is False
    assert payload["registry_integration"]["server_side_only"] is True


def test_public_security_boundary_is_layered_and_bounded() -> None:
    payload = load("public_intake_counterparty_preflight_contract.json")

    security = payload["abuse_and_security"]
    assert len(security["edge_layers"]) >= 3
    assert len(security["application_layers"]) >= 6
    assert security["anti_enumeration"]["no_unbounded_identifier_search"] is True
    assert security["anti_enumeration"]["no_detailed_registry_dump_to_public_client"] is True
    assert security["initial_control_policy"]["attachments"] == (
        "disabled_until_secure_upload_boundary_is_verified"
    )


def test_public_submission_is_idempotent_and_cannot_write_bitrix_directly() -> None:
    payload = load("public_intake_counterparty_preflight_contract.json")

    safety = payload["request_safety"]
    assert safety["idempotency_required"] is True
    assert safety["same_key_different_payload"] == "fail_closed"
    assert safety["replay_after_timeout"] == (
        "reconcile_before_creating_second_observation"
    )
    assert safety["direct_bitrix_creation_from_public_form"] is False


def test_operator_preflight_preserves_causal_lineage() -> None:
    payload = load("public_intake_counterparty_preflight_contract.json")

    assert payload["operator_preflight_card"]["ai_verdict_field"] is False
    assert payload["operator_preflight_card"]["causal_links"] == [
        "request_id",
        "correlation_id",
        "shema_identity_ref",
        "preflight_snapshot_id",
    ]


def test_provider_failure_never_becomes_fabricated_clean_status() -> None:
    payload = load("public_intake_counterparty_preflight_contract.json")

    assert payload["registry_integration"]["provider_failure"] == (
        "return UNKNOWN_PROVIDER_UNAVAILABLE_without_fabricating_status"
    )

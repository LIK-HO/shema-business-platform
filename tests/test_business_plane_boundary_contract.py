import json
from pathlib import Path


ROOT = Path(__file__).parents[1]


def load(name: str) -> dict:
    return json.loads((ROOT / "architecture" / name).read_text(encoding="utf-8"))


def test_business_plane_contract_prevents_dual_ownership() -> None:
    payload = load("business_plane_boundary_contract.json")

    assert payload["ownership_transfer"]["same_live_field_is_never_written_by_both_systems"] is True
    assert payload["domain_ownership"]["bitrix24_after_handoff"]
    assert payload["domain_ownership"]["shema"]
    assert "transaction_price" in payload["domain_ownership"]["forbidden_dual_ownership"]
    assert "business_economics" in payload["domain_ownership"]["forbidden_dual_ownership"]


def test_handoff_is_idempotent_and_reconciliation_safe() -> None:
    payload = load("business_plane_boundary_contract.json")

    assert payload["delivery"]["outbox_required"] is True
    assert payload["delivery"]["at_least_once_delivery"] is True
    assert payload["delivery"]["duplicate_safe_consumer_required"] is True
    assert payload["delivery"]["lost_response_requires_reconciliation_before_retry"] is True
    assert payload["delivery"]["same_key_different_payload_must_fail_closed"] is True
    assert payload["handoff_identity"]["stable_idempotency_key_pattern"] == (
        "bitrix-handoff:{handoff_id}"
    )


def test_shema_does_not_reimplement_repeat_orders_or_live_economics() -> None:
    payload = load("business_plane_boundary_contract.json")

    assert payload["repeat_business"]["shema_must_not_reimplement_bitrix_recurring_deal_engine"] is True
    assert payload["economics"]["no_new_live_accounting_subsystem_in_shema"] is True
    assert payload["documents"]["shema_role"] == "requirements_and_configuration_snapshot"

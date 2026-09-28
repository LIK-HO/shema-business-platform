import json
from pathlib import Path


ROOT = Path(__file__).parents[1]


def load(name: str) -> dict:
    return json.loads((ROOT / "architecture" / name).read_text(encoding="utf-8"))


def test_procurement_registry_is_provider_neutral_and_fail_closed() -> None:
    payload = load("procurement_source_registry_contract.json")

    assert payload["model"]["canonical_port"] == "ProcurementSourceAdapter"
    assert payload["model"]["registry"] == "ProcurementSourceRegistry"
    assert payload["rules"]["provider_neutral_contract_first"] is True
    assert payload["rules"]["no_implicit_provider_fallback"] is True
    assert payload["rules"]["no_html_scraping_fallback"] is True
    assert payload["rules"]["provider_outputs_are_not_canonical_identity"] is True
    assert payload["activation"]["disabled_by_default"] is True


def test_platform_strategy_keeps_business_ownership_separated() -> None:
    payload = load("platform_growth_strategy_contract.json")

    assert payload["product_boundary"]["bitrix24_role_after_maturity"] == (
        "transaction_business_process_communication_calculation_and_economics_control_plane"
    )
    assert "pricing_for_live_transactions" in payload["ownership"][
        "bitrix24_authoritative_after_handoff"
    ]
    assert "business_economics" in payload["ai"]["not_authoritative_for"]
    assert payload["max"]["live_outbound_status"].startswith(
        "blocked_until_provider"
    )


def test_yandex_cloud_strategy_does_not_create_a_second_transaction_authority() -> None:
    payload = load("platform_growth_strategy_contract.json")

    assert payload["yandex_cloud"]["canonical_database"] == "managed_postgresql"
    assert payload["yandex_cloud"]["secondary_database_policy"] == (
        "ydb_only_after_measured_constraint"
    )
    assert payload["yandex_cloud"]["async_transport"] == (
        "message_queue_only_when_transport_scaling_requires_it"
    )
    assert (
        payload["economics_boundary"]["new_shema_transaction_economics_feature_development"]
        is False
    )


def test_no_strategic_b2b_center_dependency_remains_in_manifest_or_roadmap() -> None:
    for relative_path in (
        "docs/DEVELOPMENT_MANIFEST.md",
        "docs/ROADMAP.md",
    ):
        content = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "B2B-Center is a later" not in content
        assert "B2B-Center is removed" in content


def test_strategy_preserves_two_domains_without_split_brain() -> None:
    payload = load("platform_growth_strategy_contract.json")

    assert payload["data_plane"]["shema_yandex_cloud"]["canonical_database"] == "managed_postgresql"
    assert payload["data_plane"]["bitrix24"]["authority_after_handoff"] == (
        "live_business_transactions_and_process_state"
    )
    assert payload["data_plane"]["transition_rule"].startswith(
        "do_not_migrate_the_entire_shema_database"
    )
    assert payload["operator_continuity"]["no_shadow_copy_of_live_business_state"] is True
    assert "handoff_id" in payload["operator_continuity"]["stable_context_keys"]
    assert payload["operator_continuity"]["shema_pre_handoff_assignment"].startswith(
        "Shema_may_own_preparation_assignment"
    )




def test_public_experience_is_part_of_the_platform_strategy() -> None:
    payload = load("platform_growth_strategy_contract.json")

    public_web = payload["experience_surfaces"]["public_web"]
    assert public_web["canonical_domain"] == "схемагрупп.рф"
    assert public_web["canonical_api"] is True
    assert public_web["no_live_business_authority"] is True
    assert payload["experience_surfaces"]["max_mini_app"] == (
        "same_public_web_application_inside_MAX_bot"
    )
    assert "utm" in payload["experience_surfaces"]["source_attribution"]


def test_strategy_has_no_tender_or_document_subsystem_ownership() -> None:
    payload = load("platform_growth_strategy_contract.json")

    assert "procurement_observations" not in payload["ownership"]["shema_authoritative"]
    assert "business_documents_and_approvals_where_configured" not in payload[
        "ownership"
    ]["bitrix24_authoritative_after_handoff"]
    assert "procurement_strategy" not in payload
    assert "document_evolution" not in payload

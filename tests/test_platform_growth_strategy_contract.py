import json
from pathlib import Path


ROOT = Path(__file__).parents[1]


def load(name: str) -> dict:
    return json.loads((ROOT / "architecture" / name).read_text(encoding="utf-8"))


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


def test_removed_subsystems_have_no_active_repository_surface() -> None:
    removed = (
        "architecture/gosplan_procurement_adapter_contract.json",
        "architecture/procurement_monitoring_contract.json",
        "architecture/procurement_source_registry_contract.json",
        "src/shema_platform/application/procurement.py",
        "src/shema_platform/adapters/procurement/gosplan.py",
        "tests/test_gosplan_procurement_adapter.py",
        "tests/test_procurement_contracts.py",
        "tests/test_procurement_monitoring.py",
    )

    assert all(not (ROOT / path).exists() for path in removed)


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


def test_intelligence_source_policy_is_bounded_and_question_driven() -> None:
    payload = load("intelligence_source_policy_contract.json")

    assert payload["routing_rules"]["no_all_sources_by_default"] is True
    assert payload["routing_rules"]["no_global_source_waterfall"] is True
    assert payload["routing_rules"]["specialist_sources_are_triggered_not_default"] is True
    assert payload["operator_budget"]["default_candidate_discovery_source_classes"] == 3
    assert payload["operator_modes"]["FAST"]
    assert payload["operator_modes"]["VERIFY"]
    assert payload["operator_modes"]["DEEP"]
    assert payload["operator_modes"]["MANUAL"]


def test_bitrix_setup_agent_is_bounded_to_discovery_plan_apply_verify() -> None:
    agent = json.loads(
        (
            ROOT / "architecture" / "bitrix24_configuration_agent_contract.json"
        ).read_text(encoding="utf-8")
    )

    assert agent["placement"] == "integration_business_plane_boundary"
    assert agent["core_impact"] is False
    assert agent["phases"] == [
        "DISCOVER",
        "PLAN",
        "DRY_RUN",
        "APPLY",
        "VERIFY",
        "RECONCILE",
    ]
    assert "read_only_discovery_before_mutation" in agent["safety_rules"]
    assert "direct_unreviewed_rest_mutations" in agent["ai_role"]["forbidden"]
    assert "tender_or_document_subsystem_configuration" in agent["non_goals"]

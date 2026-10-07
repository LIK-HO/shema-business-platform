import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def load() -> dict:
    return json.loads(
        (ROOT / "architecture" / "operator_interface_contract.json").read_text(
            encoding="utf-8"
        )
    )


def test_operator_shell_uses_bounded_bitrix_aligned_workspaces() -> None:
    payload = load()
    sections = payload["shell"]["left_navigation"]["primary_sections"]
    ids = {item["id"] for item in sections}
    assert {
        "workbench",
        "clients",
        "counterparties",
        "requests",
        "research",
        "repeat_orders",
        "handoffs",
        "control",
    } <= ids
    forbidden = payload["shell"]["left_navigation"]["forbidden_primary_sections"]
    assert "Сделки" in forbidden
    assert "Тендеры" in forbidden
    assert "Документы" in forbidden


def test_record_form_and_work_queue_match_mature_crm_patterns() -> None:
    payload = load()
    assert payload["work_queue"]["default_view"] == "list"
    assert "kanban" in payload["work_queue"]["alternate_views"]
    assert payload["work_queue"]["list_primitives"]
    assert payload["record_form"]["canonical_layout"] == (
        "structured_fields_left_activity_history_right"
    )
    assert payload["record_form"]["activity_history"]["server_authoritative"] is True


def test_counterparty_monitoring_and_favorites_are_distinct() -> None:
    payload = load()
    counterparty = payload["specialized_workspaces"]["counterparties"]
    assert counterparty["monitoring_is_not_favorites"] is True
    assert counterparty["favorites_are_personal_shortcuts"] is True
    assert (
        counterparty["monitoring_creates_durable_change_checks_and_notifications"]
        is True
    )


def test_repeat_orders_hide_cleanly_after_bitrix_cutover() -> None:
    payload = load()
    repeat = payload["specialized_workspaces"]["repeat_orders"]
    assert repeat["temporary_shema_live_mode_is_allowed"] is True
    assert repeat["past_orders_are_immutable"] is True
    assert repeat["bitrix_recurring_engine_is_not_reimplemented"] is True
    after = repeat["after_cutover"]
    assert after["hide_without_layout_reflow"] is True
    assert (
        payload["capability_visibility"][
            "old_deep_links_show_authorized_destination_or_explicit_moved_state"
        ]
        is True
    )


def test_ui_never_becomes_a_second_authority() -> None:
    payload = load()
    security = payload["security_and_authority"]
    assert security["ui_does_not_own_truth"] is True
    assert security["external_effects_are_not_authorized_by_visual_state_alone"] is True
    assert (
        payload["bitrix24_alignment"]["mapping_is_conceptual_not_shared_authority"]
        is True
    )


def test_untrusted_and_state_boundaries_are_explicit() -> None:
    payload = load()
    assert payload["security_and_authority"]["client_text_is_untrusted_data"] is True
    states = payload["state_presentation"]["mandatory_distinction"]
    assert "NOT_SEARCHED != NOT_FOUND" in states
    assert "UNAVAILABLE != CHANGED" in states
    assert "PENDING != COMPLETED" in states
    assert "UNKNOWN != BLOCKING" in states


def test_web_and_pwa_remain_provider_neutral_without_new_backend() -> None:
    payload = load()
    deployment = payload["deployment"]
    assert deployment["target_environment"] == "provider_neutral"
    assert deployment["operator_web"]["runtime_authority"] == "canonical_shema_api"
    assert deployment["operator_web"]["no_direct_database_access"] is True
    assert deployment["operator_pwa"]["canonical_api"] == "canonical_shema_api"
    assert deployment["operator_pwa"]["no_separate_backend"] is True
    assert deployment["operator_pwa"]["offline_storage_is_not_authoritative"] is True

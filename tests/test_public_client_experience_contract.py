import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def load() -> dict:
    return json.loads(
        (ROOT / "architecture" / "public_client_experience_contract.json").read_text(
            encoding="utf-8"
        )
    )


def test_public_web_is_the_client_intake_surface() -> None:
    payload = load()

    public_web = payload["experience_surfaces"]["public_web"]
    assert public_web["role"] == "public_company_site_and_client_request_intake"
    assert public_web["canonical_domain"] == "схемагрупп.рф"
    assert public_web["uses_canonical_api"] is True
    assert public_web["creates_live_business_order"] is False


def test_max_is_a_projection_of_the_same_public_web_application() -> None:
    payload = load()

    max_app = payload["experience_surfaces"]["max_mini_app"]
    assert max_app["requires_max_bot"] is True
    assert max_app["bot_role"] == (
        "answer_client_questions_clarify_request_and_open_request_flow"
    )
    assert max_app["static_https_url_required"] is True
    assert max_app["uses_same_public_web_application"] is True
    assert max_app["uses_same_canonical_api"] is True
    assert max_app["no_separate_business_database"] is True


def test_client_request_preserves_causal_and_source_attribution() -> None:
    payload = load()

    continuity = payload["causal_continuity"]
    assert continuity["request_id_required"] is True
    assert continuity["correlation_id_required"] is True
    assert continuity["source_attribution_preserved"] is True

    form = payload["guided_form"]
    assert "utm_source" in form["source_attribution"]
    assert "contact_channel" in form["minimum_fields"]
    assert "yandex_advertising_where_available" in payload["acquisition_channels"]
    assert "google_advertising_where_available" in payload["acquisition_channels"]
    assert "vk_advertising_where_available" in payload["acquisition_channels"]


def test_insales_domain_cutover_preserves_dns_and_mail_before_detachment() -> None:
    payload = load()

    migration = payload["domain_migration"]
    assert migration["source_platform"] == "inSales"
    assert migration["target_platform"] == "Shema Web/PWA public surface"
    assert migration["preserve_existing_dns_records"] is True
    assert migration["preserve_mail_records"] is True
    assert migration["cutover_requires_https_validation"] is True
    assert migration["inSales_detachment_after_successful_cutover"] is True

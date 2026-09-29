import json
from pathlib import Path

from fastapi.testclient import TestClient

from shema_platform.experience.api import create_app

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "shema_platform" / "experience" / "web"


def test_phase6_operator_navigation_matches_contract_scope() -> None:
    html = (WEB / "index.html").read_text(encoding="utf-8")
    allowed = (
        "workbench",
        "clients",
        "counterparties",
        "requests",
        "research",
        "repeat",
        "handoffs",
        "control",
    )
    forbidden = ("Сделки", "Счета", "Документы", "Тендеры", "Склад", "Бухгалтерия", "Персонал")
    for route in allowed:
        assert 'data-route="' + route + '"' in html
    for label in forbidden:
        assert label not in html


def test_phase6_shell_and_work_queue_primitives_are_present() -> None:
    html = (WEB / "index.html").read_text(encoding="utf-8")
    js = (WEB / "app.js").read_text(encoding="utf-8")
    for token in ("global-search", "notifications", "network-state", "workbench", "requests", "clients", "handoffs"):
        assert token in html or token in js
    for token in ("preferences", "query", "severity", "sort", "selected", "session"):
        assert token in js
    assert "view-preserve" not in js


def test_phase6_exact_identifier_search_precedes_discovery() -> None:
    js = (WEB / "app.js").read_text(encoding="utf-8")
    assert "function globalIdentifier" in js
    assert "location.hash='counterparties'" in js
    assert "AI до детерминированной проверки не вызывается" in js


def test_phase6_record_context_and_causal_links_are_explicit() -> None:
    js = (WEB / "app.js").read_text(encoding="utf-8")
    for token in (
        "ACTIVITY / HISTORY",
        "RELATED",
        "requestId",
        "Correlation",
        "to-counterparty",
        "to-handoff",
        "related-research",
    ):
        assert token in js
    assert "Raw intake не является trusted instruction." in js


def test_phase6_public_surfaces_do_not_expose_operator_navigation() -> None:
    js = (WEB / "app.js").read_text(encoding="utf-8")
    css = (WEB / "style.css").read_text(encoding="utf-8")
    assert "setSurfaceMode(true)" in js
    assert "public-mode" in css
    assert "body.public-mode .side nav" in css
    assert ".public-mode .global-search" in css
    assert ".public-mode .header-tools #notifications" in css


def test_phase6_capability_visibility_and_business_authority_rules() -> None:
    js = (WEB / "app.js").read_text(encoding="utf-8")
    for token in (
        "S.caps.repeatOrders",
        "S.caps.diagnostics",
        "server-authoritative",
        "не создаёт локальную копию бизнес-состояния",
        "Execution endpoint не скомпонован",
    ):
        assert token in js
    forbidden = (
        "localstorage",
        "sessionstorage",
        "indexeddb",
        "document.cookie",
        "database_url",
        "postgres",
    )
    lower = js.lower()
    for token in forbidden:
        assert token not in lower


def test_phase6_pwa_reuses_the_same_web_surface() -> None:
    html = (WEB / "index.html").read_text(encoding="utf-8")
    js = (WEB / "app.js").read_text(encoding="utf-8")
    assert '/web/app.js' in html
    assert '/web/style.css' in html
    assert "navigator.serviceWorker.register('/sw.js'" in js
    assert "location.origin" in js


def test_phase6_public_bootstrap_remains_same_origin_and_protected_business_api_remains_closed() -> None:
    client = TestClient(create_app(enable_docs=False))
    for path in ("/", "/request", "/max", "/sw.js", "/manifest.webmanifest"):
        response = client.get(path)
        assert response.status_code == 200
    for path in ("/v1/operator/capabilities", "/v1/orders", "/v1/economics/example"):
        response = client.get(path)
        assert response.status_code in {401, 403, 503}
        assert response.headers["Cache-Control"] == "no-store"


def test_phase6_contracts_remain_compatible() -> None:
    operator_contract = json.loads(
        (ROOT / "architecture" / "operator_interface_contract.json").read_text(encoding="utf-8")
    )
    public_contract = json.loads(
        (ROOT / "architecture" / "public_client_experience_contract.json").read_text(encoding="utf-8")
    )
    assert operator_contract["experience_surfaces"]["operator_pwa"]["same_canonical_api"] is True
    assert operator_contract["experience_surfaces"]["operator_pwa"]["no_second_business_rule_implementation"] is True
    assert public_contract["experience_surfaces"]["max_mini_app"]["uses_same_public_web_application"] is True
    assert public_contract["non_goals"].count("second_crm") == 1

from pathlib import Path

from fastapi.testclient import TestClient

from shema_platform.experience.api import create_app


def test_web_routes_are_same_origin_and_public() -> None:
    c=TestClient(create_app(enable_docs=False))
    for path in ("/","/request","/operator","/max"):
        r=c.get(path)
        assert r.status_code==200
        assert "/web/style.css" in r.text
        assert "/web/app.js" in r.text

def test_web_assets_and_client_security_contract() -> None:
    c=TestClient(create_app(enable_docs=False))
    assert c.get("/web/style.css").status_code==200
    js=c.get("/web/app.js").text
    assert "X-Bot-Challenge" in js
    assert "/v1/public/intake" in js
    assert "/v1/operator/notifications" in js
    assert "localStorage" not in js
    assert "sessionStorage" not in js
    assert "document.cookie" not in js
    assert "postgres" not in js.lower()
    assert "DATABASE_URL" not in js

def test_visual_contract_regions_exist() -> None:
    root=Path(__file__).resolve().parents[1]/"src"/"shema_platform"/"experience"/"web"
    html=(root/"index.html").read_text()
    css=(root/"style.css").read_text()
    js=(root/"app.js").read_text()
    for token in ['id="nav"','id="surface"','id="title"','id="view"','id="auth"']:
        assert token in html
    for token in [".shell",".side","header",".card",".hero","@media"]:
        assert token in css
    for token in ["pub()","requests()","searchView()","counterparties()","system()","dossier()"]:
        assert token in js

def test_public_shell_does_not_bypass_operator_api_authentication() -> None:
    client = TestClient(create_app(enable_docs=False))

    assert client.get("/operator").status_code == 200
    assert client.get("/web/app.js").status_code == 200

    notifications = client.get("/v1/operator/notifications")
    capabilities = client.get("/v1/operator/capabilities")

    assert notifications.status_code in {401, 403, 503}
    assert capabilities.status_code in {401, 403, 503}

def test_public_surface_contains_attribution_and_causal_context_contract() -> None:
    client = TestClient(create_app(enable_docs=False))
    response = client.get("/?utm_source=test&utm_medium=cpc&utm_campaign=phase4")
    assert response.status_code == 200

    js = client.get("/web/app.js").text
    for token in (
        "utmSource",
        "utmMedium",
        "utmCampaign",
        "referrer",
        "correlationId",
        "Idempotency-Key",
        "surface=max",
    ):
        assert token in js

    for service_label in ("Погрузка и разгрузка", "Такелаж и подъём", "Линейный персонал"):
        assert service_label in response.text or service_label in js

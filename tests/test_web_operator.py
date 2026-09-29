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

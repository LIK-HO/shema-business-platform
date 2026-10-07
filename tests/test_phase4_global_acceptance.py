from pathlib import Path

from fastapi.testclient import TestClient

from shema_platform.experience.api import create_app


def test_phase4_global_acceptance_surface_and_trust_boundaries() -> None:
    client = TestClient(create_app(enable_docs=False))

    public_routes = ("/", "/request", "/operator", "/system", "/max")
    for path in public_routes:
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Cache-Control"] == "no-store"
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]

    for asset in ("/web/style.css", "/web/app.js"):
        response = client.get(asset)
        assert response.status_code == 200
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    for protected_path in (
        "/v1/operator/capabilities",
        "/v1/operator/notifications",
        "/v1/diagnostics",
        "/v1/intelligence/counterparties/monitoring",
        "/v1/intelligence/counterparties/favorites",
    ):
        response = client.get(protected_path)
        assert response.status_code in {401, 403, 503}
        assert response.headers["Cache-Control"] == "no-store"

    js = client.get("/web/app.js").text.lower()
    forbidden_client_authority = (
        "localstorage",
        "sessionstorage",
        "indexeddb",
        "document.cookie",
        "database_url",
        "postgres",
    )
    for token in forbidden_client_authority:
        assert token not in js

    required_surfaces = (
        "pub()",
        "requests()",
        "searchview()",
        "counterparties()",
        "system()",
        "dossier()",
        "workbench()",
        "repeat()",
    )
    for token in required_surfaces:
        assert token in js


def test_phase4_global_acceptance_uses_one_same_origin_web_application() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "shema_platform" / "experience"
    html = (root / "web" / "index.html").read_text(encoding="utf-8")
    js = (root / "web" / "app.js").read_text(encoding="utf-8")

    assert '/web/app.js' in html
    assert '/web/style.css' in html
    assert "api('/v1/" in js
    assert "window.SHEMA_BOT_CHALLENGE_TOKEN" in js
    assert "location.origin" in js

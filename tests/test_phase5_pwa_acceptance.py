import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
WEB = ROOT / "src" / "shema_platform" / "experience" / "web"
CONTRACT = ROOT / "architecture" / "pwa_contract.json"


def test_pwa_contract_is_explicit():
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert data["same_origin"] is True
    assert data["service_worker"]["scope"] == "/"
    assert data["service_worker"]["cache_only_public_assets"] is True
    assert data["service_worker"]["network_only_business_api"] is True
    assert data["offline"]["memory_only_pending_queue"] is True
    assert data["offline"]["max_pending_items"] == 8
    assert data["offline"]["authorization_headers_never_queued"] is True
    assert data["offline"]["mutation_requires_idempotency_key"] is True


def test_manifest_is_installable_and_same_origin():
    manifest = json.loads((WEB / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["display"] == "standalone"
    assert manifest["scope"] == "/"
    assert manifest["start_url"] == "/"
    assert len(manifest["icons"]) >= 2
    assert {icon["sizes"] for icon in manifest["icons"]} >= {"192x192", "512x512"}
    assert all(icon["src"].startswith("/web/") for icon in manifest["icons"])


def test_service_worker_is_public_only_and_versioned():
    sw = (WEB / "sw.js").read_text(encoding="utf-8")
    assert 'CACHE_VERSION = "shema-pwa-v1"' in sw
    assert '"/v1/"' in sw
    assert 'url.pathname.startsWith("/health/")' in sw
    assert 'self.skipWaiting()' in sw
    assert 'event.request' in sw
    assert 'request.mode === "navigate"' in sw


def test_client_has_no_persistent_browser_authority():
    js = (WEB / "app.js").read_text(encoding="utf-8").lower()
    forbidden_terms = (
        "localstorage",
        "sessionstorage",
        "indexeddb",
        "document.cookie",
        "database_url",
        "postgres",
    )
    for forbidden in forbidden_terms:
        assert forbidden not in js


def test_client_offline_queue_is_bounded_memory_only():
    js = (WEB / "app.js").read_text(encoding="utf-8")
    assert "pendingQueue" in js
    assert "MAX_PENDING = 8" in js
    assert "Idempotency-Key" in js
    assert "Authorization" in js


def test_web_surface_exposes_manifest_and_service_worker():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    web_py = (ROOT / "src" / "shema_platform" / "experience" / "web.py").read_text(encoding="utf-8")
    assert 'rel="manifest"' in html
    assert "/sw.js" in html
    assert '"/sw.js"' in web_py
    assert '"/manifest.webmanifest"' in web_py

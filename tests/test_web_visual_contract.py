from pathlib import Path
from fastapi.testclient import TestClient
from shema_platform.experience.api import create_app

def test_web_visual_contract_duplicate_removed() -> None:
    c=TestClient(create_app(enable_docs=False))
    for path in ("/","/request","/operator","/max"):
        r=c.get(path)
        assert r.status_code==200
        assert "/web/style.css" in r.text
        assert "/web/app.js" in r.text


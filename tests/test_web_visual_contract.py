from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parents[1] / "src" / "shema_platform" / "experience" / "web"


def test_critical_visual_contract_regions() -> None:
    root = _root()
    html = (root / "index.html").read_text()
    css = (root / "style.css").read_text()
    js = (root / "app.js").read_text()
    for token in ['id="nav"', 'id="surface"', 'id="title"', 'id="view"', 'id="auth"', 'id="toast"']:
        assert token in html
    assert '/web/scheme.svg' in html
    assert 'alt="СХЕМА"' in html
    assert (root / "scheme.svg").is_file()
    assert not (root / "scheme.png").exists()
    for token in [".shell", ".side", "header", ".card", ".hero", ".table", "@media"]:
        assert token in css
    for token in [
        "pub()",
        "requests()",
        "searchView()",
        "counterparties()",
        "system()",
        "dossier()",
        "workbench()",
        "repeat()",
    ]:
        assert token in js
    assert "localStorage" not in js
    assert "sessionStorage" not in js

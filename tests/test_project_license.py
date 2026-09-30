import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_project_license_is_explicit_and_present() -> None:
    content = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "Apache License" in content
    assert "Version 2.0, January 2004" in content
    assert "END OF TERMS AND CONDITIONS" in content


def test_project_metadata_declares_apache_license() -> None:
    project = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]
    assert project["license"]["text"] == "Apache-2.0"

import pathlib

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_release_tree_matches_current_core_baseline() -> None:
    from shema_platform.platform.release import validate_release_tree

    manifest = validate_release_tree(ROOT)

    assert manifest.application_version == "1.5.0"
    assert manifest.kernel_contract_version == "1.4"
    assert manifest.core_maturity_contract_version == "1.5-core-maturity"
    assert manifest.latest_migration_version == 9


def test_release_tree_fails_when_maturity_gate_set_changes(tmp_path) -> None:
    from shema_platform.platform.release import ReleaseContractError, validate_release_tree
    for source in (
        "architecture/contract.json",
        "architecture/core_maturity_contract.json",
        "pyproject.toml",
    ):
        target = tmp_path / source
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            (ROOT / source).read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    contract = tmp_path / "architecture" / "core_maturity_contract.json"
    text = contract.read_text(encoding="utf-8").replace(
        '"release_safety",',
        '"release_safety",\n        "unexpected_gate",',
    )
    contract.write_text(text, encoding="utf-8")

    migrations = tmp_path / "db" / "migrations"
    migrations.mkdir(parents=True)
    for path in sorted((ROOT / "db" / "migrations").glob("*.sql")):
        (migrations / path.name).write_text(
            path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    with pytest.raises(ReleaseContractError, match="gates"):
        validate_release_tree(tmp_path)

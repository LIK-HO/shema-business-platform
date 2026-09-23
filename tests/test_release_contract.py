import json
from pathlib import Path

from shema_platform.platform.release import (
    ReleaseContractError,
    validate_release_tree,
)


def test_release_tree_matches_current_core_baseline() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = validate_release_tree(root)

    assert manifest.application_version == "1.5.0"
    assert manifest.kernel_contract_version == "1.4"
    assert manifest.core_maturity_contract_version == "1.5-core-maturity"
    assert manifest.release_candidate_contract_version == "1.5-release-candidate-contract"
    assert manifest.latest_migration_version == 9


def test_release_tree_fails_when_maturity_gate_set_changes(tmp_path) -> None:
    root = Path(__file__).resolve().parents[1]
    for source in (
        "architecture/contract.json",
        "architecture/core_maturity_contract.json",
        "architecture/release_candidate_contract.json",
        "architecture/slo_contract.json",
        "architecture/capacity_overload_contract.json",
        "docs/SECURITY_CERTIFICATION_MATRIX.md",
        "docs/SLO_ERROR_BUDGET.md",
        "docs/CAPACITY_OVERLOAD.md",
        "scripts/postgres_pitr_drill.sh",
        ".github/workflows/ci.yml",
        "pyproject.toml",
    ):
        target = tmp_path / source
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            (root / source).read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    contract = tmp_path / "architecture" / "core_maturity_contract.json"
    payload = json.loads(contract.read_text(encoding="utf-8"))
    payload["maturity_gates"].append("unexpected_gate")
    contract.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    migrations = tmp_path / "db" / "migrations"
    migrations.mkdir(parents=True)
    for path in sorted((root / "db" / "migrations").glob("*.sql")):
        (migrations / path.name).write_text(
            path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    try:
        validate_release_tree(tmp_path)
    except ReleaseContractError as exc:
        assert "gates" in str(exc)
    else:
        raise AssertionError("expected release contract gate failure")

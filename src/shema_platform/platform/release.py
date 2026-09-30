from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from shema_platform.platform.migrations import MigrationPlan, MigrationPlanError


class ReleaseContractError(RuntimeError):
    """The repository cannot be released from the current source tree."""


@dataclass(frozen=True, slots=True)
class ReleaseManifest:
    application_version: str
    kernel_contract_version: str
    core_maturity_contract_version: str
    release_candidate_contract_version: str
    latest_migration_version: int


def _read_json(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseContractError(f"invalid release contract: {path}") from exc


def _project_version(pyproject: Path) -> str:
    text = pyproject.read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', text, re.MULTILINE)
    if match is None:
        raise ReleaseContractError("project version is missing")
    return match.group(1)


def validate_release_tree(root: Path) -> ReleaseManifest:
    contract = _read_json(root / "architecture" / "contract.json")
    maturity = _read_json(root / "architecture" / "core_maturity_contract.json")
    candidate = _read_json(root / "architecture" / "release_candidate_contract.json")

    if contract.get("version") != "1.4":
        raise ReleaseContractError("frozen kernel contract must remain version 1.4")
    if maturity.get("version") != "1.5-core-maturity":
        raise ReleaseContractError("core maturity contract version mismatch")
    if candidate.get("version") != "1.5-release-candidate-contract":
        raise ReleaseContractError("release candidate contract version mismatch")
    if candidate.get("release_version") != "1.5.0":
        raise ReleaseContractError("release candidate version must remain 1.5.0")
    if candidate.get("frozen_kernel_contract_version") != contract.get("version"):
        raise ReleaseContractError("release candidate kernel contract mismatch")
    if candidate.get("core_maturity_contract_version") != maturity.get("version"):
        raise ReleaseContractError("release candidate maturity contract mismatch")
    required_certification = {"B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9"}
    if set(candidate.get("required_certification_elements", ())) != required_certification:
        raise ReleaseContractError("release candidate certification boundary is incomplete")
    required_controls = candidate.get("required_release_controls", ())
    required_control_paths = {
        "architecture_contract": root / "architecture" / "contract.json",
        "core_maturity_contract": root / "architecture" / "core_maturity_contract.json",
        "migration_baseline": root / "db" / "migrations" / "0009_state_ownership_invariants.sql",
        "security_certification_matrix": root / "docs" / "SECURITY_CERTIFICATION_MATRIX.md",
        "slo_error_budget_baseline": root / "architecture" / "slo_contract.json",
        "capacity_overload_baseline": root / "architecture" / "capacity_overload_contract.json",
        "backup_recovery_drill": root / "scripts" / "postgres_pitr_drill.sh",
        "supply_chain_audit": root / ".github" / "workflows" / "ci.yml",
    }
    if set(required_controls) != set(required_control_paths):
        raise ReleaseContractError("release control set is incomplete or changed unexpectedly")
    missing_controls = [
        name for name, path in required_control_paths.items() if not path.is_file()
    ]
    if missing_controls:
        raise ReleaseContractError(
            "release controls are missing: " + ", ".join(sorted(missing_controls))
        )

    freeze_policy = candidate.get("final_freeze_policy", {})
    required_freeze_flags = (
        "kernel_semantics_frozen_after_green_release_candidate",
        "new_features_stay_outside_core",
        "core_change_requires_proven_invariant_or_security_or_data_integrity_or_fundamental_reliability_defect",
        "core_change_requires_regression_tests",
        "core_change_requires_impact_analysis",
        "core_change_requires_rollback_plan",
    )
    if any(freeze_policy.get(flag) is not True for flag in required_freeze_flags):
        raise ReleaseContractError("final freeze policy is incomplete")

    required_gates = {
        "correctness",
        "atomicity",
        "concurrency",
        "recovery",
        "security",
        "observability",
        "release_safety",
    }
    actual_gates = set(maturity.get("maturity_gates", ()))
    if actual_gates != required_gates:
        raise ReleaseContractError(
            "core maturity gates are incomplete or changed unexpectedly"
        )

    latest_required = maturity.get("migration_safety", {}).get("latest_required_version")
    if latest_required != 9:
        raise ReleaseContractError("migration release baseline must be version 9")

    try:
        plan = MigrationPlan.from_directory(root / "db" / "migrations")
    except MigrationPlanError as exc:
        raise ReleaseContractError(str(exc)) from exc

    if not plan.migrations or plan.migrations[-1].version != latest_required:
        raise ReleaseContractError("migration plan does not match release baseline")

    application_version = _project_version(root / "pyproject.toml")
    if application_version != "1.5.0":
        raise ReleaseContractError("application version must remain 1.5.0")

    return ReleaseManifest(
        application_version=application_version,
        kernel_contract_version=str(contract["version"]),
        core_maturity_contract_version=str(maturity["version"]),
        release_candidate_contract_version=str(candidate["version"]),
        latest_migration_version=plan.migrations[-1].version,
    )


def main() -> int:
    validate_release_tree(Path(__file__).resolve().parents[3])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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

    if contract.get("version") != "1.4":
        raise ReleaseContractError("frozen kernel contract must remain version 1.4")
    if maturity.get("version") != "1.5-core-maturity":
        raise ReleaseContractError("core maturity contract version mismatch")

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
        latest_migration_version=plan.migrations[-1].version,
    )


def main() -> int:
    validate_release_tree(Path(__file__).resolve().parents[3])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

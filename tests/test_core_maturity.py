import json
import pathlib

import pytest

from shema_platform.platform.migrations import (
    Migration,
    MigrationIntegrityError,
    MigrationPlan,
    MigrationPlanError,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_core_maturity_contract_is_explicit() -> None:
    contract = json.loads((ROOT / "architecture/core_maturity_contract.json").read_text())
    assert contract["version"] == "1.5-core-maturity"
    assert contract["maturity_gates"] == [
        "correctness",
        "atomicity",
        "concurrency",
        "recovery",
        "security",
        "observability",
        "release_safety",
    ]
    assert contract["migration_safety"]["historical_edit_fails_closed"] is True


def test_migration_plan_rejects_gaps() -> None:
    with pytest.raises(MigrationPlanError, match="contiguous"):
        MigrationPlan((
            Migration(1, "foundation", "create table a (id integer);"),
            Migration(3, "later", "create table c (id integer);"),
        ))


def test_migration_checksum_is_deterministic() -> None:
    migration = Migration(1, "foundation", "create table a (id integer);")
    assert migration.checksum == Migration(
        1, "foundation", "create table a (id integer);"
    ).checksum


def test_migration_integrity_error_is_a_distinct_fail_closed_error() -> None:
    assert issubclass(MigrationIntegrityError, RuntimeError)

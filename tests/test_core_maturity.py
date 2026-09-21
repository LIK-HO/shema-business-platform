import json
from pathlib import Path

import pytest

from shema_platform.platform import migrations


ROOT = Path(__file__).resolve().parents[1]


def test_core_maturity_contract_is_explicit() -> None:
    contract = json.loads(
        (ROOT / "architecture/core_maturity_contract.json").read_text()
    )
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
    assert contract["canonical_critical_workflows"] == [
        "commercial_action_create",
        "order_create",
    ]
    assert contract["critical_workflows_require"] == [
        "canonical_postgresql_identity_lookup",
        "explicit_operation_idempotency_key",
        "business_state_idempotency_outbox_audit_atomic_commit",
    ]
    assert contract["database_state_ownership_constraints"] is True
    assert contract["migration_safety"]["historical_edit_fails_closed"] is True
    assert contract["migration_safety"]["latest_required_version"] == 9
    migration = (
        ROOT / "db/migrations/0009_state_ownership_invariants.sql"
    ).read_text()
    assert "job_execution_lease_consistency_check" in migration
    assert "outbox_delivery_lease_consistency_check" in migration
    assert "commercial_action_send_lease_check" in migration


def test_migration_plan_rejects_gaps() -> None:
    with pytest.raises(migrations.MigrationPlanError, match="contiguous"):
        migrations.MigrationPlan(
            (
                migrations.Migration(
                    1,
                    "foundation",
                    "create table a (id integer);",
                ),
                migrations.Migration(
                    3,
                    "later",
                    "create table c (id integer);",
                ),
            )
        )


def test_migration_checksum_is_deterministic() -> None:
    migration = migrations.Migration(
        1,
        "foundation",
        "create table a (id integer);",
    )
    assert migration.checksum == migrations.Migration(
        1,
        "foundation",
        "create table a (id integer);",
    ).checksum


def test_migration_integrity_error_is_a_distinct_fail_closed_error() -> None:
    assert issubclass(migrations.MigrationIntegrityError, RuntimeError)

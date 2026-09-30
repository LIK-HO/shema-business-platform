import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read_contract() -> dict:
    return json.loads(
        (ROOT / "architecture" / "phase7c_live_evidence_contract.json").read_text(
            encoding="utf-8"
        )
    )

def test_phase7c_is_distinct_from_verified_7b() -> None:
    contract = read_contract()
    assert contract["status"] == "phase7c_in_progress"
    assert contract["sub_boundary"] == "7C_CLOUD_RESOURCE_PROVISIONING_AND_LIVE_EVIDENCE"

def test_phase7c_preserves_authority_boundaries() -> None:
    contract = read_contract()
    assert contract["authority_invariants"]["transactional_state"] == "managed_postgresql"
    assert contract["authority_invariants"]["business_reliability_plane"] == (
        "postgresql_outbox_and_durable_jobs"
    )
    assert contract["safety_gates"]["no_second_transactional_authority"] is True

def test_phase7c_requires_live_recovery_and_production_evidence() -> None:
    required = set(read_contract()["required_live_evidence"])
    assert {
        "terraform_apply_success",
        "database_connection_and_migrations_verified_from_same_vpc",
        "health_and_readiness_verified",
        "observability_verified",
        "budget_and_alerts_verified",
        "backup_retention_verified",
        "pitr_recovery_drill_verified",
        "rollback_to_previous_immutable_revision_verified",
        "production_smoke_verified",
        "final_current_head_seven_job_gate_green",
    }.issubset(required)

def test_phase7c_requires_externalized_credentials_and_manual_apply() -> None:
    gates = read_contract()["safety_gates"]
    assert gates["real_credentials_must_be_externalized"] is True
    assert gates["apply_requires_manual_dispatch"] is True
    assert gates["live_evidence_must_not_contain_secret_values"] is True

def test_phase7c_does_not_create_a_debug_database_endpoint() -> None:
    constraint = read_contract()["known_environment_constraint"]
    assert "same VPC" in constraint
    assert "debug/database-probe endpoint" in constraint

def test_phase7c_recovery_baseline_is_present_in_terraform() -> None:
    main = (ROOT / "deploy" / "terraform" / "main.tf").read_text(encoding="utf-8")
    assert "deletion_protection = true" in main
    assert "backup_retain_period_days = 14" in main
    assert "backup_window_start = {" in main


def test_phase7c_live_probe_does_not_claim_database_connectivity() -> None:
    script = (ROOT / "scripts" / "yandex_cloud_live_evidence.sh").read_text(encoding="utf-8")
    assert "DATABASE_CONNECTIVITY_AND_MIGRATIONS=NOT_CLAIMED" in script

def test_phase7c_uses_private_task_runner_for_same_vpc_migrations() -> None:
    main = (ROOT / "deploy" / "terraform" / "main.tf").read_text(encoding="utf-8")
    variables = (ROOT / "deploy" / "terraform" / "variables.tf").read_text(encoding="utf-8")
    probe = (
        ROOT / "src" / "shema_platform" / "platform" / "live_migration_probe.py"
    ).read_text(encoding="utf-8")
    assert 'runtime {' in main
    assert 'type = "task"' in main
    assert 'type = "task"' in main
    assert "migration_runner_name" in variables
    assert "shema_platform.platform.live_migration_probe" in main
    assert "MigrationRunner" in probe
    assert "DATABASE_URL" in probe


def test_phase7c_migration_runner_is_not_publicly_exposed() -> None:
    main = (ROOT / "deploy" / "terraform" / "main.tf").read_text(encoding="utf-8")
    assert "allow-unauthenticated-invoke" not in main
    assert "api_gateway" not in main.split('resource "yandex_serverless_container" "migration_runner"', 1)[1]

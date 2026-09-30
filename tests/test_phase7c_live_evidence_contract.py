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


def test_phase7c_live_probe_claims_database_connectivity_only_after_task_success() -> None:
    script = (ROOT / "scripts" / "yandex_cloud_live_evidence.sh").read_text(encoding="utf-8")
    assert '[[ "$task_exit_code" == "0" ]]' in script
    assert "DATABASE_CONNECTIVITY_AND_MIGRATIONS=PASS" in script

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
    migration_runner_section = main.split(
        'resource "yandex_serverless_container" "migration_runner"', 1
    )[1]
    assert "api_gateway" not in migration_runner_section

def test_phase7c_contract_binds_same_vpc_task_runner_and_forbids_public_access() -> None:
    contract = read_contract()
    execution = contract["execution"]
    assert execution["migration_runner_runtime"] == "task"
    assert execution["migration_runner_network"] == "same_vpc_as_managed_postgresql"
    assert execution["migration_runner_access"] == "containerInvoker_only_for_ci_identity"
    assert execution["migration_runner_endpoint"] == "no_api_gateway; no_public_access"
    assert contract["safety_gates"]["migration_task_must_not_be_public"] is True

def test_phase7c_provisions_explicit_runtime_database_and_user() -> None:
    main = (ROOT / "deploy" / "terraform" / "main.tf").read_text(encoding="utf-8")
    variables = (ROOT / "deploy" / "terraform" / "variables.tf").read_text(encoding="utf-8")
    assert 'resource "yandex_mdb_postgresql_database" "runtime"' in main
    assert 'resource "yandex_mdb_postgresql_user" "runtime"' in main
    assert "password_wo" in main
    assert "var.database_secret_input" in main
    assert "database_name" in variables
    assert "database_user" in variables
    assert "database_secret_input" in variables


def test_phase7c_rollback_drill_is_reversible_and_immutable() -> None:
    contract = read_contract()
    drill = contract["execution"]["rollback_drill"]
    assert drill["mode"] == "protected_manual_input"
    assert "capture_previous_active_revision_before_apply" in drill["sequence"]
    assert "rollback_to_previous_immutable_revision" in drill["sequence"]
    assert "restore_new_immutable_revision" in drill["sequence"]
    assert contract["safety_gates"]["rollback_must_restore_current_revision"] is True


def test_phase7c_rollback_script_uses_yandex_immutable_revision_rollback() -> None:
    script = (ROOT / "scripts" / "yandex_cloud_rollback_drill.sh").read_text(
        encoding="utf-8"
    )
    assert "yc serverless container rollback" in script
    assert "PREVIOUS_REVISION_ID" in script
    assert 'NEW_REVISION_ID="$(active_revision)"' in script
    assert "ROLLBACK_TO_PREVIOUS=PASS" in script
    assert "ROLLBACK_RESTORE_CURRENT=PASS" in script


def test_phase7c_workflow_exposes_protected_rollback_drill_input() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "phase7c-live-provisioning.yml"
    ).read_text(encoding="utf-8")
    assert "rollback_drill:" in workflow
    assert "inputs.rollback_drill == true" in workflow
    assert "needs.plan.outputs.previous_revision_id" in workflow
    assert "yandex_cloud_rollback_drill.sh" in workflow

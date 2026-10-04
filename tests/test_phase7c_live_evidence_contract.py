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

def test_phase7c_requires_persistent_terraform_state_controls() -> None:
    contract = read_contract()
    assert "terraform_state_backend_verified" in contract["required_live_evidence"]
    assert contract["safety_gates"]["terraform_state_must_be_remote"] is True
    assert contract["safety_gates"]["terraform_state_bucket_versioning_required"] is True
    assert contract["safety_gates"]["terraform_state_lockfile_must_be_enabled"] is True
    assert contract["execution"]["terraform_state"]["backend"] == "yandex_object_storage_s3"
    assert contract["execution"]["terraform_state"]["locking"] == "s3_lockfile"


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
    assert "BACKUP_RETENTION=PASS" in script
    assert "PRODUCTION_SMOKE=PASS" in script

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


def test_phase7c_pitr_contract_is_isolated_and_reversible() -> None:
    contract = read_contract()
    drill = contract["execution"]["pitr_drill"]
    assert drill["recovery_target"] == "new_temporary_prestable_managed_postgresql_cluster"
    assert drill["recovery_network"] == "same_vpc_as_production"
    assert drill["recovery_host_public_ip"] is False
    assert drill["recovery_credentials"] == (
        "temporary_lockbox_secret_derived_from_protected_production_database_url"
    )
    assert drill["production_mutation"] == "none"
    gates = contract["safety_gates"]
    assert gates["pitr_must_restore_to_separate_cluster"] is True
    assert gates["pitr_must_not_mutate_production"] is True
    assert gates["pitr_recovery_credentials_must_use_lockbox"] is True
    assert gates["pitr_cleanup_must_run_on_success_and_failure"] is True


def test_phase7c_pitr_script_restores_private_cluster_and_cleans_up() -> None:
    script = (ROOT / "scripts" / "yandex_cloud_pitr_drill.sh").read_text(
        encoding="utf-8"
    )
    assert "yc managed-postgresql cluster restore" in script
    assert "--environment PRESTABLE" in script
    assert 'assign-public-ip=false' in script
    assert '--deletion-protection=false' in script
    assert 'recovery_delete_target="$RECOVERY_CLUSTER_ID"' in script
    assert 'recovery_delete_target="$RECOVERY_CLUSTER_NAME"' in script
    assert 'yc lockbox secret create' in script
    assert '--payload -' in script
    assert '--payload "$payload"' not in script
    assert 'yc serverless container revision deploy' in script
    assert '--runtime task' in script
    assert 'PITR_PRODUCTION_MUTATION=NONE' in script
    assert "trap 'exit 143' INT TERM" in script
    assert 'trap cleanup EXIT' in script
    assert 'PITR_RECOVERY_CLEANUP=PASS' in script
    assert 'PITR_RECOVERY_CLEANUP=FAIL' in script
    assert 'yc managed-postgresql cluster delete' in script


def test_phase7c_pitr_script_uses_same_immutable_image_digest() -> None:
    script = (ROOT / "scripts" / "yandex_cloud_pitr_drill.sh").read_text(
        encoding="utf-8"
    )
    assert 'IMAGE_DIGEST=' in script
    assert 'IMAGE_URL@$IMAGE_DIGEST' in script
    assert 'PITR_RECOVERY_DATABASE_CONNECTIVITY=PASS' in script


def test_phase7c_pitr_script_proves_private_same_vpc_recovery() -> None:
    script = (ROOT / "scripts" / "yandex_cloud_pitr_drill.sh").read_text(
        encoding="utf-8"
    )
    assert '.network_id == $network' in script
    assert 'assign_public_ip' in script
    assert 'PITR_RECOVERY_SAME_VPC=PASS' in script
    assert 'PITR_RECOVERY_NO_PUBLIC_IP=PASS' in script


def test_phase7c_pitr_exposes_only_bounded_invoker_identity() -> None:
    outputs = (ROOT / "deploy" / "terraform" / "outputs.tf").read_text(encoding="utf-8")
    assert 'output "container_puller_service_account_id"' in outputs
    assert 'yandex_iam_service_account.container_puller.id' in outputs


def test_phase7c_workflow_exposes_protected_pitr_input() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "phase7c-live-provisioning.yml"
    ).read_text(encoding="utf-8")
    assert "pitr_drill:" in workflow
    assert "pitr_recovery_time:" in workflow
    assert "inputs.pitr_drill == true" in workflow
    assert "yandex_cloud_pitr_drill.sh" in workflow
    assert "container_puller_service_account_id" in workflow
    assert "PITR_DATABASE_URL" in workflow


def test_phase7c_live_evidence_uses_approved_edge_and_immutable_artifact() -> None:
    script = (ROOT / "scripts" / "yandex_cloud_live_evidence.sh").read_text(
        encoding="utf-8"
    )
    assert "YC_API_GATEWAY_ID" in script
    assert 'yc serverless api-gateway get --id "$YC_API_GATEWAY_ID"' in script
    assert 'API_URL="https://$API_GATEWAY_DOMAIN"' in script
    assert "YC_EXPECTED_IMAGE_DIGEST" in script
    assert "IMMUTABLE_IMAGE_DIGEST=PASS" in script
    workflow = (
        ROOT / ".github" / "workflows" / "phase7c-live-provisioning.yml"
    ).read_text(encoding="utf-8")
    assert 'terraform -chdir=deploy/terraform output -raw api_gateway_id' in workflow
    assert 'values.get("image_digest")' in workflow


def test_phase7c_live_evidence_requires_budget_thresholds_and_runtime_logs() -> None:
    script = (ROOT / "scripts" / "yandex_cloud_live_evidence.sh").read_text(
        encoding="utf-8"
    )
    assert "BUDGET_THRESHOLDS=PASS" in script
    assert "RUNTIME_AND_TASK_LOGGING=PASS" in script
    contract = read_contract()
    required = set(contract["required_live_evidence"])
    assert "api_gateway_edge_ready" in required
    assert "immutable_image_digest_verified" in required
    assert "budget_thresholds_verified" in required
    assert "runtime_and_task_observability_verified" in required


def test_phase7c_terraform_backend_is_remote_and_locked() -> None:
    versions = (ROOT / "deploy" / "terraform" / "versions.tf").read_text(encoding="utf-8")
    assert 'backend "s3"' in versions
    assert 's3 = "https://storage.yandexcloud.net"' in versions
    assert "use_lockfile" in versions
    assert 'shema/production/terraform.tfstate' in versions


def test_phase7c_workflow_binds_apply_to_reviewed_plan_fingerprint() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "phase7c-live-provisioning.yml"
    ).read_text(encoding="utf-8")
    assert "planned_change_fingerprint" in workflow
    assert "Recompute and verify reviewed Terraform plan" in workflow
    assert 'test "$actual_fingerprint" = "$EXPECTED_PLAN_FINGERPRINT"' in workflow
    apply_command = (
        'terraform -chdir=deploy/terraform '
        'apply -input=false "$RUNNER_TEMP/phase7c.tfplan"'
    )
    assert apply_command in workflow


def test_phase7c_state_preflight_requires_versioning() -> None:
    script = (
        ROOT / "scripts" / "yandex_cloud_terraform_state_preflight.sh"
    ).read_text(encoding="utf-8")
    assert "YC_TERRAFORM_STATE_BUCKET" in script
    assert "VERSIONING_ENABLED" in script
    assert "TERRAFORM_STATE_BUCKET_SECRET_VALUES=NOT_PRINTED" in script


def test_phase7c_workflow_has_one_state_preflight_per_execution_job() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "phase7c-live-provisioning.yml"
    ).read_text(encoding="utf-8")
    plan = workflow.split("\n  apply:\n    needs: plan", 1)[0]
    apply = workflow.split("\n  apply:\n    needs: plan", 1)[1]
    assert plan.count("Verify persistent Terraform state backend") == 1
    assert apply.split("      - name: Collect live resource evidence", 1)[0].count(
        "Verify persistent Terraform state backend"
    ) == 1


def test_phase7c_requires_production_network_and_database_connectivity_evidence() -> None:
    contract = read_contract()
    required = set(contract["required_live_evidence"])
    assert {
        "all_availability_zone_subnets_verified",
        "postgresql_ha_hosts_verified",
        "private_postgresql_security_group_verified",
        "postgresql_tls_verified",
        "credential_rotation_version_verified",
    }.issubset(required)
    assert contract["safety_gates"]["private_postgresql_only"] is True
    assert contract["safety_gates"]["postgresql_tls_verification_required"] is True

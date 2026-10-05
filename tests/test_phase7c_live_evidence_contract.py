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


def test_phase7c_audit_trail_delivery_uses_writer_role() -> None:
    terraform = (ROOT / "deploy" / "terraform" / "main.tf").read_text(
        encoding="utf-8"
    )
    assert 'role      = "logging.writer"' in terraform
    assert 'role      = "logging.viewer"' not in terraform

def test_phase7c_live_evidence_requires_mature_observability_controls() -> None:
    script = (ROOT / "scripts" / "yandex_cloud_live_evidence.sh").read_text(
        encoding="utf-8"
    )
    for marker in (
        "YC_RUNTIME_LOG_GROUP_ID",
        "YC_AUDIT_LOG_GROUP_ID",
        "YC_AUDIT_TRAIL_ID",
        "YC_REGISTRY_ID",
        "APP_NAME",
        "RUNTIME_LOG_GROUP=PASS",
        "AUDIT_LOG_GROUP=PASS",
        "AUDIT_TRAIL=PASS",
        "REGISTRY_SCAN_POLICY=PASS",
        "REGISTRY_VULNERABILITY_SCAN_POLICY=PASS",
    ):
        assert marker in script

    contract = read_contract()
    required = set(contract["required_live_evidence"])
    assert {
        "runtime_log_group_verified",
        "audit_log_group_verified",
        "audit_trail_verified",
        "registry_vulnerability_scan_policy_verified",
    }.issubset(required)
    gates = contract["safety_gates"]
    assert gates["custom_runtime_log_group_required"] is True
    assert gates["audit_trail_required"] is True
    assert gates["registry_vulnerability_scanning_required"] is True
    assert contract["execution"]["observability"]["retention_hours_minimum"] >= 720

def test_phase7c_live_evidence_workflow_passes_dedicated_state_credentials() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "phase7c-live-provisioning.yml"
    ).read_text(encoding="utf-8")
    block = workflow.split("Collect live resource evidence", 1)[1].split(
        "bash scripts/yandex_cloud_live_evidence.sh", 1
    )[0]
    assert "PHASE7C_TERRAFORM_STATE_ACCESS_KEY_ID" in block
    assert "PHASE7C_TERRAFORM_STATE_SECRET_KEY" in block
    assert 'terraform -chdir=deploy/terraform output -raw runtime_log_group_id' in block
    assert 'terraform -chdir=deploy/terraform output -raw audit_log_group_id' in block
    assert 'terraform -chdir=deploy/terraform output -raw audit_trail_id' in block
    assert 'terraform -chdir=deploy/terraform output -raw registry_id' in block

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


def test_phase7c_registry_pull_access_uses_native_cli_boundary() -> None:
    main = (ROOT / "deploy" / "terraform" / "main.tf").read_text(encoding="utf-8")
    script = (
        ROOT / "scripts" / "yandex_cloud_container_registry_access.sh"
    ).read_text(encoding="utf-8")
    assert 'resource "yandex_container_registry_iam_binding" "puller"' not in main
    assert 'resource "terraform_data" "container_registry_pull_access"' in main
    assert 'bash ../../scripts/yandex_cloud_container_registry_access.sh ensure' in main
    assert "yc container registry add-access-binding" in script
    assert "container-registry.images.puller" in script
    assert "CONTAINER_REGISTRY_PULL_ACCESS=PASS" in script


def test_phase7c_existing_bucket_is_imported_before_plan() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "phase7c-live-provisioning.yml"
    ).read_text(encoding="utf-8")
    assert "yc storage bucket get --name" in workflow
    assert (
        "terraform -chdir=deploy/terraform import -input=false "
        "yandex_storage_bucket.bounded_objects"
    ) in workflow


def test_phase7c_api_gateway_waits_for_invoker_and_service_account_use() -> None:
    main = (ROOT / "deploy" / "terraform" / "main.tf").read_text(encoding="utf-8")
    variables = (ROOT / "deploy" / "terraform" / "variables.tf").read_text(encoding="utf-8")
    workflow = (
        ROOT / ".github" / "workflows" / "phase7c-live-provisioning.yml"
    ).read_text(encoding="utf-8")
    assert 'role      = "iam.serviceAccounts.user"' in main
    assert 'role      = "container-registry.admin"' in main
    assert "yandex_serverless_container_iam_member.gateway_invoker" in main
    assert "yandex_resourcemanager_folder_iam_member.deployment_service_account_user" in main
    assert "deployment_service_account_id" in variables
    assert 'values["deployment_service_account_id"]' in workflow


def test_phase7c_bounded_bucket_uses_private_platform_default_without_acl_mutation() -> None:
    main = (ROOT / "deploy" / "terraform" / "main.tf").read_text(encoding="utf-8")
    assert 'resource "yandex_storage_bucket" "bounded_objects"' in main
    assert 'resource "yandex_storage_bucket_grant"' not in main
    assert 'public-' not in main


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


def test_phase7c_state_preflight_requires_versioning_and_dedicated_credentials() -> None:
    script = (
        ROOT / "scripts" / "yandex_cloud_terraform_state_preflight.sh"
    ).read_text(encoding="utf-8")
    assert "YC_TERRAFORM_STATE_BUCKET" in script
    assert "AWS_ACCESS_KEY_ID" in script
    assert "AWS_SECRET_ACCESS_KEY" in script
    assert "AWS_DEFAULT_REGION" in script
    assert "AWS CLI" in script
    assert "run_s3 head-bucket" in script
    assert "get-bucket-versioning" in script
    assert 'versioning" != "Enabled"' in script
    assert "TERRAFORM_STATE_CREDENTIAL_ISOLATION=PASS" in script
    assert "TERRAFORM_STATE_CREDENTIAL_VALUES=NOT_PRINTED" in script

def test_phase7c_state_preflight_does_not_depend_on_deployment_identity() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "phase7c-live-provisioning.yml"
    ).read_text(encoding="utf-8")
    assert workflow.count(
        "Verify persistent Terraform state backend"
    ) == 2
    assert workflow.count(
        "AWS_ACCESS_KEY_ID: ${{ secrets.PHASE7C_TERRAFORM_STATE_ACCESS_KEY_ID }}"
    ) >= 2
    assert workflow.count(
        "AWS_SECRET_ACCESS_KEY: ${{ secrets.PHASE7C_TERRAFORM_STATE_SECRET_KEY }}"
    ) >= 2
    assert workflow.count("AWS_DEFAULT_REGION: ru-central1") >= 2


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


def test_phase7c_digest_guard_uses_bash_regex_syntax() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "phase7c-live-provisioning.yml"
    ).read_text(encoding="utf-8")
    assert '[[ "$image_digest" =~ ^sha256:[0-9a-f]{64}$ ]]' in workflow
    assert 'test "$image_digest" =~' not in workflow


def test_phase7c_registry_image_listing_accepts_object_and_array_payloads() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "phase7c-live-provisioning.yml"
    ).read_text(encoding="utf-8")
    jq_expression = '(if type == "object" then (.images // []) else . end)[]?'
    assert workflow.count(jq_expression) == 3
    assert '(.images // .)[]?' not in workflow


def test_phase7c_terraform_steps_receive_yandex_provider_key() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "phase7c-live-provisioning.yml"
    ).read_text(encoding="utf-8")
    assert workflow.count("YC_SERVICE_ACCOUNT_KEY_FILE: ${{ runner.temp }}/yc/key.json") == 6
    assert workflow.count("Verify deployment identity IAM baseline") == 2
    assert workflow.count("Terraform plan") >= 1
    assert workflow.count("Terraform apply reviewed plan") == 1
    assert "Bootstrap registry and publish immutable application image" in workflow
    assert "Terraform plan" in workflow
    assert "Recompute and verify reviewed Terraform plan" in workflow
    assert "Terraform apply reviewed plan" in workflow


def test_phase7c_uses_container_registry_scan_policy_contract() -> None:
    main = (ROOT / "deploy" / "terraform" / "main.tf").read_text(encoding="utf-8")
    outputs = (ROOT / "deploy" / "terraform" / "outputs.tf").read_text(encoding="utf-8")
    bootstrap = (
        ROOT / "scripts" / "yandex_cloud_container_registry_scan_policy.sh"
    ).read_text(encoding="utf-8")
    workflow = (
        ROOT / ".github" / "workflows" / "phase7c-live-provisioning.yml"
    ).read_text(encoding="utf-8")
    contract = read_contract()

    assert 'resource "yandex_container_registry" "app"' in main
    assert "yandex_cloudregistry_scan_policy" not in main
    assert "registry_scan_policy_id" not in outputs
    assert "container-registry.api.cloud.yandex.net/container-registry/v1" in bootstrap
    assert 'repositoryPrefixes: ["*"]' in bootstrap
    assert 'rescanPeriod: "86400s"' in bootstrap
    assert "Scan policy not found for registry" in bootstrap
    assert "scanPolicyForRegistryNotFoundException" in bootstrap
    assert 'yc iam create-token' in bootstrap
    registry_policy_contract = contract["execution"]["observability"]["registry_scan_policy"]
    assert "yandex_cloudregistry_scan_policy.app" not in registry_policy_contract
    assert contract["execution"]["observability"]["registry_scan_policy"] == (
        "container_registry_scan_policy_via_official_api"
    )
    assert "yandex_cloudregistry" not in (
        ROOT / "scripts" / "yandex_cloud_live_evidence.sh"
    ).read_text(encoding="utf-8")
    assert 'bash scripts/yandex_cloud_container_registry_scan_policy.sh ensure' in workflow


def test_phase7c_scan_policy_live_evidence_uses_registry_id_not_terraform_policy_output() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "phase7c-live-provisioning.yml"
    ).read_text(encoding="utf-8")
    evidence = (
        ROOT / "scripts" / "yandex_cloud_live_evidence.sh"
    ).read_text(encoding="utf-8")
    assert 'output -raw registry_id' in workflow
    assert 'output -raw registry_scan_policy_id' not in workflow
    assert 'YC_REGISTRY_ID' in evidence
    assert 'APP_NAME' in evidence
    assert 'bash scripts/yandex_cloud_container_registry_scan_policy.sh verify' in evidence


def test_phase7c_has_fail_closed_deployment_iam_preflight() -> None:
    script = (ROOT / "scripts" / "yandex_cloud_iam_preflight.sh").read_text(
        encoding="utf-8"
    )
    workflow = (
        ROOT / ".github" / "workflows" / "phase7c-live-provisioning.yml"
    ).read_text(encoding="utf-8")
    assert "YC_SERVICE_ACCOUNT_KEY_FILE" in script
    assert "resource-manager folder list-access-bindings" in script
    assert "resource-manager cloud list-access-bindings" in script
    assert "IAM_FOLDER_BINDINGS_READ=FAIL" in script
    assert "IAM_CLOUD_BINDINGS_READ=SKIPPED" in script
    assert "IAM_CLOUD_BINDINGS_REASON=FOLDER_SCOPE_IS_DEPLOYMENT_AUTHORITY" in script
    assert "IAM_PREFLIGHT=PASS" in script
    assert "IAM_PREFLIGHT=FAIL" in script
    assert workflow.count("Verify deployment identity IAM baseline") == 2
    assert workflow.count("bash scripts/yandex_cloud_iam_preflight.sh") == 2

def test_phase7c_iam_preflight_requires_vpc_use_and_forbids_primitive_admin_fallbacks() -> None:
    script = (ROOT / "scripts" / "yandex_cloud_iam_preflight.sh").read_text(
        encoding="utf-8"
    )
    assert "require_role_set VPC_USE vpc.user vpc.admin" in script
    assert "require_role_set VPC_NETWORK vpc.privateAdmin vpc.admin" in script
    assert "require_role_set VPC_SECURITY_GROUPS vpc.securityGroups.admin vpc.admin" in script
    assert "require_role_set SERVICE_ACCOUNTS iam.serviceAccounts.admin iam.admin" in script
    assert (
        "require_role_set SERVICE_ACCOUNT_USE "
        "iam.serviceAccounts.user iam.serviceAccounts.admin iam.admin"
    ) in script
    assert (
        "require_role_set SERVERLESS_CONTAINERS "
        "serverless-containers.editor serverless-containers.admin "
        "serverless.containers.editor serverless.containers.admin"
    ) in script
    assert (
        "require_role_set SERVERLESS_CONTAINER_IAM "
        "serverless-containers.admin serverless.containers.admin"
    ) in script
    assert "require_role_set FOLDER_IAM_MANAGEMENT resource-manager.admin" in script
    assert " resource-manager.clouds.owner" not in script
    assert "require_role_set OBJECT_STORAGE storage.editor" in script
def test_phase7c_api_gateway_openapi_template_renders_runtime_identities() -> None:
    template = (ROOT / "deploy" / "terraform" / "openapi.yaml.tftpl").read_text(
        encoding="utf-8"
    )
    assert 'container_id: "${' + "container_id" + '}"' in template
    assert 'service_account_id: "${' + "container_service_account" + '}"' in template
    assert '$${container_id}' not in template
    assert '$${container_service_account}' not in template

def test_phase7c_live_evidence_treats_cloud_scope_read_as_informational() -> None:
    script = (ROOT / "scripts" / "yandex_cloud_live_evidence.sh").read_text(
        encoding="utf-8"
    )
    assert 'yc resource-manager cloud get "$YC_CLOUD_ID"' in script
    assert 'CLOUD_METADATA_READ=SKIPPED' in script
    assert 'CLOUD_METADATA_READ_REASON=FOLDER_SCOPE_IS_DEPLOYMENT_AUTHORITY' in script
    assert 'CLOUD_FOLDER_RELATION=PASS' in script
    assert ".cloud_id // .cloudId" in script

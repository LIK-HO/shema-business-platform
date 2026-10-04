import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_phase7_contract_keeps_postgres_as_canonical_authority() -> None:
    contract = json.loads(
        (ROOT / "architecture" / "yandex_cloud_production_contract.json").read_text(
            encoding="utf-8"
        )
    )
    assert contract["frozen_kernel_impact"] is False
    assert contract["authority"]["transactional_state"] == "managed_postgresql"
    assert contract["authority"]["business_reliability_plane"] == (
        "postgresql_outbox_and_durable_jobs"
    )
    assert "yandex_message_queue_as_transactional_business_store" in (
        contract["forbidden_authorities"]
    )


def test_phase7_container_boot_is_production_safe() -> None:
    dockerfile = read("Dockerfile")
    assert "APP_ENV=production" in dockerfile
    assert "--factory" not in dockerfile
    assert "shema_platform.experience.production:app" in dockerfile
    assert "--proxy-headers" in dockerfile
    assert "USER shema" in dockerfile
    assert "latest" not in dockerfile.lower()


def test_phase7_terraform_is_pinned_and_digest_based() -> None:
    versions = read("deploy/terraform/versions.tf")
    main = read("deploy/terraform/main.tf")
    assert 'source  = "yandex-cloud/yandex"' in versions
    assert 'version = "0.230.0"' in versions
    assert "digest = var.image_digest" in main
    assert "yandex_serverless_container" in main
    assert "log_options" in main
    assert 'for_each       = local.subnet_cidrs' in main
    assert 'security_group_ids  = [yandex_vpc_security_group.postgres.id]' in main
    assert 'availability_zones' in main
    assert "yandex_api_gateway" in main
    assert "yandex_mdb_postgresql_cluster_v2" in main
    assert 'primary = {' in main
    assert 'replica = {' in main
    assert 'port=6432' in main or ':6432/' in main
    assert 'sslmode=verify-full' in main
    assert 'sslrootcert=/etc/shema/yandex-cloud-ca.pem' in main
    assert 'target_session_attrs=read-write' in main


def test_phase7_terraform_separates_runtime_and_artifact_roles() -> None:
    main = read("deploy/terraform/main.tf")
    assert "yandex_iam_service_account.container_runtime" in main
    assert "yandex_iam_service_account.container_puller" in main
    assert "lockbox.payloadViewer" in main
    assert "container-registry.images.puller" in main


def test_phase7_gateway_is_the_public_edge() -> None:
    main = read("deploy/terraform/main.tf")
    spec = read("deploy/terraform/openapi.yaml.tftpl")
    assert "yandex_api_gateway" in main
    assert "type: serverless_containers" in spec
    assert "container_id" in spec
    assert "service_account_id" in spec


def test_phase7_object_storage_is_bounded_non_authoritative() -> None:
    contract = read("architecture/yandex_cloud_production_contract.json")
    assert '"orders"' in contract
    assert '"idempotency"' in contract
    assert '"outbox_truth"' in contract
    assert '"cloud_monitoring_as_business_state"' in contract


def test_phase7_parameterized_inputs_do_not_commit_real_credentials() -> None:
    tfvars = read("deploy/terraform/terraform.tfvars.example")
    assert "REPLACE_ME" in tfvars
    assert "REPLACE_IN_PROTECTED_ENV" in tfvars
    assert 'image_url      = ""' in tfvars
    assert 'image_digest   = ""' in tfvars
    assert "database_url" not in tfvars

    main = read("deploy/terraform/main.tf")
    assert "local.database_url" in main
    assert "DATABASE_URL" in main


def test_phase7_runtime_image_contains_migration_assets_without_secrets() -> None:
    dockerfile = read("Dockerfile")
    assert "COPY db ./db" in dockerfile
    assert "Lockbox" not in dockerfile
    assert "DATABASE_URL=" not in dockerfile
    assert "OIDC_" not in dockerfile


def test_phase7_exit_conditions_include_recovery_observability_and_rollback() -> None:
    contract = json.loads(
        (ROOT / "architecture" / "yandex_cloud_production_contract.json").read_text(
            encoding="utf-8"
        )
    )
    required = {
        "database_connection_and_migrations_verified",
        "secrets_verified",
        "health_and_readiness_verified",
        "observability_verified",
        "backup_and_recovery_verified",
        "rollback_verified",
        "full_current_head_release_gate_green",
        "global_adversarial_review_complete",
    }
    assert required.issubset(set(contract["exit_conditions"]))


def test_phase7_production_app_has_docs_disabled() -> None:
    from shema_platform.experience.production import app

    assert app.openapi_url is None
    assert app.docs_url is None
    assert app.redoc_url is None


def test_phase7_runtime_and_gateway_identities_are_separated() -> None:
    main = read("deploy/terraform/main.tf")
    spec = read("deploy/terraform/openapi.yaml.tftpl")
    assert 'resource "yandex_iam_service_account" "gateway_invoker"' in main
    assert 'role         = "serverless-containers.containerInvoker"' in main
    assert "serviceAccount:${yandex_iam_service_account.container_runtime.id}" in main
    assert "service_account_id = yandex_iam_service_account.container_runtime.id" in main
    assert "container_service_account = yandex_iam_service_account.gateway_invoker.id" in main
    assert 'service_account_id: "$${container_service_account}"' in spec


def test_phase7_production_import_uses_production_safe_api_entrypoint() -> None:
    import os
    import subprocess
    import sys

    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": "production",
            "OIDC_ISSUER": "https://issuer.example",
            "OIDC_AUDIENCE": "shema-test",
            "OIDC_JWKS_URL": "https://issuer.example/jwks",
            "DATABASE_URL": "postgresql://user:pass@example:6432/shema",
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", "import shema_platform.experience.api"],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

def test_phase7_contract_names_gateway_identity_role() -> None:
    contract = json.loads(
        (ROOT / "architecture" / "yandex_cloud_production_contract.json").read_text(
            encoding="utf-8"
        )
    )
    assert "gateway_invoker" in contract["iam"]["runtime_service_accounts"]
    assert contract["iam"]["role_model"]["gateway_invoker"] == (
        "API Gateway only; serverless-containers.containerInvoker on the private API container"
    )


def test_phase7_postgres_network_is_private_and_scoped() -> None:
    main = read("deploy/terraform/main.tf")
    assert 'resource "yandex_vpc_security_group" "postgres"' in main
    assert 'port           = 6432' in main
    assert 'v4_cidr_blocks = ["198.19.0.0/16"]' in main
    cluster_block = main.split('resource "yandex_mdb_postgresql_cluster_v2" "prod"', 1)[1]
    cluster_block = cluster_block.split('resource "yandex_mdb_postgresql_user"', 1)[0]
    assert 'assign_public_ip' not in cluster_block


def test_phase7_database_password_rotation_is_explicit() -> None:
    main = read("deploy/terraform/main.tf")
    variables = read("deploy/terraform/variables.tf")
    assert "password_wo_version = var.database_secret_version" in main
    assert 'variable "database_secret_version"' in variables


def test_phase7_runtime_image_contains_yandex_cloud_ca() -> None:
    dockerfile = read("Dockerfile")
    assert "cloud-certs/CA.pem" in dockerfile
    assert "/etc/ssl/certs/yandex-cloud-ca.pem" in dockerfile
    assert "curl --fail --silent --show-error --location" in dockerfile


def test_phase7_network_has_all_yandex_availability_zones() -> None:
    variables = read("deploy/terraform/variables.tf")
    assert '["ru-central1-d", "ru-central1-b", "ru-central1-a"]' in variables
    assert "length(distinct(var.availability_zones)) == 3" in variables

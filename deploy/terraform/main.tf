locals {
  common_labels = {
    project     = var.app_name
    environment = "production"
    authority   = "shema-canonical"
  }

  availability_zones = var.availability_zones
  subnet_cidrs = {
    for index, zone in local.availability_zones :
    zone => cidrsubnet("10.20.0.0/21", 3, index)
  }

  database_url = format(
    "postgresql://%s:%s@c-%s.rw.mdb.yandexcloud.net:6432/%s?sslmode=verify-full&sslrootcert=/etc/shema/yandex-cloud-ca.pem&target_session_attrs=read-write",
    var.database_user,
    urlencode(var.database_secret_input),
    yandex_mdb_postgresql_cluster_v2.prod.id,
    var.database_name,
  )
}

resource "yandex_vpc_network" "prod" {
  name   = "${var.app_name}-prod"
  labels = local.common_labels
}

resource "yandex_vpc_subnet" "runtime" {
  for_each       = local.subnet_cidrs
  name           = "${var.app_name}-runtime-${each.key}"
  zone           = each.key
  network_id     = yandex_vpc_network.prod.id
  v4_cidr_blocks = [each.value]
}

resource "yandex_vpc_security_group" "postgres" {
  name        = "${var.app_name}-postgres"
  description = "Private PostgreSQL access from the canonical runtime network only."
  network_id  = yandex_vpc_network.prod.id
  labels      = local.common_labels

  ingress {
    protocol       = "TCP"
    description    = "PostgreSQL/ODYSSEY from private Shema subnets only."
    v4_cidr_blocks = ["198.19.0.0/16"]
    port           = 6432
  }

  egress {
    protocol       = "ANY"
    description    = "Required managed database egress."
    v4_cidr_blocks = ["0.0.0.0/0"]
    from_port      = 0
    to_port        = 65535
  }
}

resource "yandex_iam_service_account" "container_runtime" {
  name        = "${var.app_name}-container-runtime"
  description = "Runtime identity for the Shema canonical API container."
}

resource "yandex_iam_service_account" "container_puller" {
  name        = "${var.app_name}-container-puller"
  description = "CI/inspection identity for registry image access."
}

resource "yandex_iam_service_account" "gateway_invoker" {
  name        = "${var.app_name}-gateway-invoker"
  description = "Least-privilege identity used only by API Gateway to invoke the private container."
}

resource "yandex_iam_service_account" "migration_runner" {
  count       = var.evidence_runner_enabled ? 1 : 0
  name        = var.migration_runner_name
  description = "Bounded same-VPC task runner for production migration and live database evidence."
}

resource "yandex_iam_service_account" "audit_trail" {
  name        = "${var.app_name}-audit-trail"
  description = "Least-privilege identity used by Yandex Audit Trails to collect and deliver audit events."
}

resource "yandex_logging_group" "runtime" {
  name             = "${var.app_name}-runtime"
  folder_id        = var.folder_id
  retention_period = "720h"
}

resource "yandex_logging_group" "audit" {
  name             = "${var.app_name}-audit"
  folder_id        = var.folder_id
  retention_period = "720h"
}

resource "yandex_resourcemanager_folder_iam_member" "audit_trail_viewer" {
  folder_id = var.folder_id
  role      = "audit-trails.viewer"
  member    = "serviceAccount:${yandex_iam_service_account.audit_trail.id}"
}

resource "yandex_resourcemanager_folder_iam_member" "audit_logging_viewer" {
  folder_id = var.folder_id
  role      = "logging.viewer"
  member    = "serviceAccount:${yandex_iam_service_account.audit_trail.id}"
}

resource "yandex_container_registry" "app" {
  name   = "${var.app_name}-images"
  labels = local.common_labels
}

resource "yandex_cloudregistry_scan_policy" "app" {
  registry_id        = yandex_container_registry.app.id
  name               = "${var.app_name}-image-scan"
  description        = "Production vulnerability scanning on push plus daily rescan."
  disabled           = false
  scan_lang_packages = true

  rules {
    push_rule {
      disabled = false
      paths    = ["*"]
    }

    schedule_rules {
      disabled      = false
      amount        = 1
      interval_unit = "day"
      paths         = ["*"]
    }
  }
}

resource "yandex_container_registry_iam_binding" "puller" {
  registry_id = yandex_container_registry.app.id
  role        = "container-registry.images.puller"
  members = concat(
    [
      "serviceAccount:${yandex_iam_service_account.container_puller.id}",
      "serviceAccount:${yandex_iam_service_account.container_runtime.id}",
    ],
    var.evidence_runner_enabled ? [
      "serviceAccount:${yandex_iam_service_account.migration_runner[0].id}",
    ] : [],
  )
}

resource "yandex_lockbox_secret" "runtime" {
  name                = "${var.app_name}-runtime"
  description         = "Production runtime secret payload."
  deletion_protection = true
  labels              = local.common_labels
}

resource "yandex_lockbox_secret_version_hashed" "runtime" {
  secret_id    = yandex_lockbox_secret.runtime.id
  key_1        = "OIDC_ISSUER"
  text_value_1 = var.oidc_issuer
  key_2        = "OIDC_AUDIENCE"
  text_value_2 = var.oidc_audience
  key_3        = "OIDC_JWKS_URL"
  text_value_3 = var.oidc_jwks_url
  key_4        = "DATABASE_URL"
  text_value_4 = local.database_url
}

resource "yandex_lockbox_secret_iam_member" "runtime" {
  secret_id = yandex_lockbox_secret.runtime.id
  role      = "lockbox.payloadViewer"
  member    = "serviceAccount:${yandex_iam_service_account.container_runtime.id}"
}

resource "yandex_audit_trails_trail" "production" {
  name               = "${var.app_name}-production"
  folder_id          = var.folder_id
  description        = "Production management and Object Storage audit events."
  service_account_id = yandex_iam_service_account.audit_trail.id

  logging_destination {
    log_group_id = yandex_logging_group.audit.id
  }

  filtering_policy {
    management_events_filter {
      resource_scope {
        resource_id   = var.folder_id
        resource_type = "resource-manager.folder"
      }
    }

    data_events_filter {
      service = "storage"

      resource_scope {
        resource_id   = var.folder_id
        resource_type = "resource-manager.folder"
      }
    }
  }

  depends_on = [
    yandex_resourcemanager_folder_iam_member.audit_trail_viewer,
    yandex_resourcemanager_folder_iam_member.audit_logging_viewer,
  ]
}

resource "yandex_mdb_postgresql_cluster_v2" "prod" {
  name                = "${var.app_name}-prod"
  environment         = "PRODUCTION"
  network_id          = yandex_vpc_network.prod.id
  security_group_ids  = [yandex_vpc_security_group.postgres.id]
  deletion_protection = true

  config {
    version                   = 17
    backup_retain_period_days = 14

    backup_window_start = {
      hours   = 2
      minutes = 30
    }

    resources {
      resource_preset_id = "s2.micro"
      disk_type_id       = "network-ssd"
      disk_size          = 32
    }
  }

  hosts = {
    primary = {
      zone      = local.availability_zones[0]
      subnet_id = yandex_vpc_subnet.runtime[local.availability_zones[0]].id
    }
    replica = {
      zone      = local.availability_zones[1]
      subnet_id = yandex_vpc_subnet.runtime[local.availability_zones[1]].id
    }
  }
}

resource "yandex_mdb_postgresql_user" "runtime" {
  cluster_id          = yandex_mdb_postgresql_cluster_v2.prod.id
  name                = var.database_user
  password_wo         = var.database_secret_input
  password_wo_version = var.database_secret_version
}

resource "yandex_mdb_postgresql_database" "runtime" {
  cluster_id = yandex_mdb_postgresql_cluster_v2.prod.id
  name       = var.database_name
  owner      = yandex_mdb_postgresql_user.runtime.name
}

resource "yandex_storage_bucket" "bounded_objects" {
  bucket                = var.bucket_name
  folder_id             = var.folder_id
  acl                   = "private"
  default_storage_class = "STANDARD"
  force_destroy         = false
  tags                  = local.common_labels
}

resource "yandex_serverless_container" "api" {
  name               = "${var.app_name}-api"
  description        = "Canonical Shema API runtime."
  memory             = 512
  execution_timeout  = "30s"
  cores              = 1
  core_fraction      = 100
  concurrency        = 8
  service_account_id = yandex_iam_service_account.container_runtime.id
  folder_id          = var.folder_id

  log_options {
    log_group_id = yandex_logging_group.runtime.id
    min_level    = "INFO"
  }

  image {
    url    = var.image_url
    digest = var.image_digest
    environment = {
      APP_ENV = "production"
    }
  }

  lifecycle {
    precondition {
      condition     = trimspace(var.image_url) != ""
      error_message = "image_url must be populated by the protected deployment bootstrap."
    }
    precondition {
      condition     = can(regex("^sha256:[0-9a-f]{64}$", var.image_digest))
      error_message = "image_digest must be an exact sha256 digest populated by the protected deployment bootstrap."
    }
  }

  connectivity {
    network_id = yandex_vpc_network.prod.id
  }

  secrets {
    id                   = yandex_lockbox_secret.runtime.id
    version_id           = yandex_lockbox_secret_version_hashed.runtime.id
    key                  = "OIDC_ISSUER"
    environment_variable = "OIDC_ISSUER"
  }

  secrets {
    id                   = yandex_lockbox_secret.runtime.id
    version_id           = yandex_lockbox_secret_version_hashed.runtime.id
    key                  = "OIDC_AUDIENCE"
    environment_variable = "OIDC_AUDIENCE"
  }

  secrets {
    id                   = yandex_lockbox_secret.runtime.id
    version_id           = yandex_lockbox_secret_version_hashed.runtime.id
    key                  = "OIDC_JWKS_URL"
    environment_variable = "OIDC_JWKS_URL"
  }

  secrets {
    id                   = yandex_lockbox_secret.runtime.id
    version_id           = yandex_lockbox_secret_version_hashed.runtime.id
    key                  = "DATABASE_URL"
    environment_variable = "DATABASE_URL"
  }
}

resource "yandex_serverless_container_iam_member" "gateway_invoker" {
  container_id = yandex_serverless_container.api.id
  role         = "serverless-containers.containerInvoker"
  member       = "serviceAccount:${yandex_iam_service_account.gateway_invoker.id}"
}

resource "yandex_api_gateway" "edge" {
  name        = "${var.app_name}-edge"
  description = "Canonical public edge for the Shema API."

  connectivity {
    network_id = yandex_vpc_network.prod.id
  }

  dynamic "custom_domains" {
    for_each = trimspace(var.custom_domain) != "" && trimspace(var.custom_domain_certificate_id) != "" ? [1] : []

    content {
      fqdn           = trimspace(var.custom_domain)
      certificate_id = trimspace(var.custom_domain_certificate_id)
    }
  }

  lifecycle {
    precondition {
      condition = (
        trimspace(var.custom_domain) == "" ||
        trimspace(var.custom_domain_certificate_id) != ""
      )
      error_message = "custom_domain_certificate_id is required when custom_domain is configured."
    }
  }

  spec = templatefile("${path.module}/openapi.yaml.tftpl", {
    container_id              = yandex_serverless_container.api.id
    container_service_account = yandex_iam_service_account.gateway_invoker.id
  })
}

resource "yandex_lockbox_secret_iam_member" "migration_runner" {
  count     = var.evidence_runner_enabled ? 1 : 0
  secret_id = yandex_lockbox_secret.runtime.id
  role      = "lockbox.payloadViewer"
  member    = "serviceAccount:${yandex_iam_service_account.migration_runner[0].id}"
}

resource "yandex_serverless_container" "migration_runner" {
  count              = var.evidence_runner_enabled ? 1 : 0
  name               = var.migration_runner_name
  description        = "Bounded same-VPC migration and live database evidence task runner."
  memory             = 512
  execution_timeout  = "120s"
  cores              = 1
  core_fraction      = 100
  concurrency        = 1
  service_account_id = yandex_iam_service_account.migration_runner[0].id
  folder_id          = var.folder_id

  runtime {
    type = "task"
  }

  log_options {
    log_group_id = yandex_logging_group.runtime.id
    min_level    = "INFO"
  }

  image {
    url     = var.image_url
    digest  = var.image_digest
    command = ["python", "-m", "shema_platform.platform.live_migration_probe"]
    environment = {
      APP_ENV = "production"
    }
  }

  connectivity {
    network_id = yandex_vpc_network.prod.id
  }

  secrets {
    id                   = yandex_lockbox_secret.runtime.id
    version_id           = yandex_lockbox_secret_version_hashed.runtime.id
    key                  = "DATABASE_URL"
    environment_variable = "DATABASE_URL"
  }
}

resource "yandex_serverless_container_iam_member" "migration_runner_invoker" {
  count        = var.evidence_runner_enabled ? 1 : 0
  container_id = yandex_serverless_container.migration_runner[0].id
  role         = "serverless-containers.containerInvoker"
  member       = "serviceAccount:${yandex_iam_service_account.container_puller.id}"
}

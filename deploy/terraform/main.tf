locals {
  common_labels = {
    project     = var.app_name
    environment = "production"
    authority   = "shema-canonical"
  }
}

resource "yandex_vpc_network" "prod" {
  name   = "${var.app_name}-prod"
  labels = local.common_labels
}

resource "yandex_vpc_subnet" "runtime" {
  name           = "${var.app_name}-runtime"
  zone           = var.zone
  network_id     = yandex_vpc_network.prod.id
  v4_cidr_blocks = ["10.20.0.0/24"]
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

resource "yandex_container_registry" "app" {
  name   = "${var.app_name}-images"
  labels = local.common_labels
}

resource "yandex_container_registry_iam_binding" "puller" {
  registry_id = yandex_container_registry.app.id
  role        = "container-registry.images.puller"
  members = [
    "serviceAccount:${yandex_iam_service_account.container_puller.id}",
    "serviceAccount:${yandex_iam_service_account.container_runtime.id}",
  ]
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
  text_value_4 = var.database_url
}

resource "yandex_lockbox_secret_iam_member" "runtime" {
  secret_id = yandex_lockbox_secret.runtime.id
  role      = "lockbox.payloadViewer"
  member    = "serviceAccount:${yandex_iam_service_account.container_runtime.id}"
}

resource "yandex_mdb_postgresql_cluster_v2" "prod" {
  name        = "${var.app_name}-prod"
  environment = "PRODUCTION"
  network_id  = yandex_vpc_network.prod.id

  config {
    version = 17

    resources {
      resource_preset_id = "s2.micro"
      disk_type_id       = "network-ssd"
      disk_size          = 32
    }
  }

  hosts = {
    primary = {
      zone      = var.zone
      subnet_id = yandex_vpc_subnet.runtime.id
    }
  }
}

resource "yandex_storage_bucket" "bounded_objects" {
  bucket                = var.bucket_name
  folder_id             = var.folder_id
  acl                   = "private"
  default_storage_class = "STANDARD"
  force_destroy         = false
  labels                = local.common_labels
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

  environment = {
    APP_ENV = "production"
  }

  image {
    url    = var.image_url
    digest = var.image_digest
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

  spec = templatefile("${path.module}/openapi.yaml.tftpl", {
    container_id             = yandex_serverless_container.api.id
    container_service_account = yandex_iam_service_account.gateway_invoker.id
  })
}

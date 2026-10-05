variable "cloud_id" {
  type        = string
  description = "Yandex Cloud ID."
  sensitive   = true
}

variable "folder_id" {
  type        = string
  description = "Yandex Cloud folder ID."
  sensitive   = true
}

variable "deployment_service_account_id" {
  type        = string
  description = "Service account ID used by the protected deployment workflow."
  sensitive   = true
}

variable "zone" {
  type        = string
  description = "Primary availability zone."
  default     = "ru-central1-d"
}

variable "availability_zones" {
  type        = list(string)
  description = "All availability zones required by a user network; first two host the production PostgreSQL HA pair."
  default     = ["ru-central1-d", "ru-central1-b", "ru-central1-a"]

  validation {
    condition = (
      length(var.availability_zones) == 3 &&
      length(distinct(var.availability_zones)) == 3 &&
      alltrue([
        for zone in var.availability_zones : contains(
          ["ru-central1-a", "ru-central1-b", "ru-central1-d"],
          zone
        )
      ])
    )
    error_message = "availability_zones must contain ru-central1-a, ru-central1-b and ru-central1-d exactly once."
  }
}

variable "app_name" {
  type    = string
  default = "shema"
}

variable "image_url" {
  type        = string
  description = "Container Registry image URL. Filled by the protected deployment bootstrap."
  default     = ""
}

variable "image_digest" {
  type        = string
  description = "Exact sha256 digest of the deployed image. Filled by the protected deployment bootstrap."
  default     = ""
}

variable "oidc_issuer" {
  type      = string
  sensitive = true
}

variable "oidc_audience" {
  type      = string
  sensitive = true
}

variable "oidc_jwks_url" {
  type      = string
  sensitive = true
}

variable "bucket_name" {
  type        = string
  description = "Private Object Storage bucket for bounded large objects."
}

variable "custom_domain" {
  type        = string
  description = "Optional public hostname."
  default     = ""
}

variable "custom_domain_certificate_id" {
  type        = string
  description = "Optional Certificate Manager certificate ID for the custom API Gateway domain."
  default     = ""
}

variable "evidence_runner_enabled" {
  type        = bool
  description = "Enable the private same-VPC task runner used only for live migration/database evidence."
  default     = false
}

variable "migration_runner_name" {
  type        = string
  description = "Name of the bounded same-VPC migration evidence runner."
  default     = "shema-migration-runner"
}

variable "database_name" {
  type        = string
  description = "Canonical transactional PostgreSQL database name."
  default     = "shema"
}

variable "database_user" {
  type        = string
  description = "Canonical transactional PostgreSQL runtime user."
  default     = "shema_runtime"
}

variable "database_secret_input" {
  type        = string
  description = "Write-only value for the canonical PostgreSQL runtime credential; supplied only through the protected operator environment."
  sensitive   = true
}

variable "database_secret_version" {
  type        = number
  description = "Monotonic version for the write-only PostgreSQL credential. Increment when the protected credential changes."
  default     = 1

  validation {
    condition     = var.database_secret_version >= 1 && floor(var.database_secret_version) == var.database_secret_version
    error_message = "database_secret_version must be a positive integer and must be incremented for credential rotation."
  }
}

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

variable "zone" {
  type        = string
  description = "Primary availability zone."
  default     = "ru-central1-d"
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

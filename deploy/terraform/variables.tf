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
  description = "Container Registry image URL."
}

variable "image_digest" {
  type        = string
  description = "Exact sha256 digest of the deployed image."
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

variable "database_url" {
  type        = string
  description = "Managed PostgreSQL DSN delivered through Lockbox."
  sensitive   = true
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

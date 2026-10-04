output "registry_id" {
  value = yandex_container_registry.app.id
}

output "container_id" {
  value = yandex_serverless_container.api.id
}

output "container_revision_id" {
  value = yandex_serverless_container.api.revision_id
}

output "api_gateway_id" {
  value = yandex_api_gateway.edge.id
}

output "postgres_cluster_id" {
  value = yandex_mdb_postgresql_cluster_v2.prod.id
}

output "private_bucket_name" {
  value = yandex_storage_bucket.bounded_objects.bucket
}

output "migration_runner_id" {
  value = try(yandex_serverless_container.migration_runner[0].id, null)
}

output "migration_runner_revision_id" {
  value = try(yandex_serverless_container.migration_runner[0].revision_id, null)
}

output "container_puller_service_account_id" {
  value = yandex_iam_service_account.container_puller.id
}

output "database_url" {
  value     = local.database_url
  sensitive = true
}

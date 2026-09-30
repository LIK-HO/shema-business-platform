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

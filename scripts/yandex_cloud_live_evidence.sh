#!/usr/bin/env bash
set -Eeuo pipefail

for name in YC_CLOUD_ID YC_FOLDER_ID YC_CONTAINER_NAME YC_CLUSTER_NAME YC_BUCKET_NAME YC_BUDGET_ID; do
  eval "value=\$$name"
  test -n "$value" || { echo "missing required live evidence input: $name" >&2; exit 1; }
done

command -v yc >/dev/null || { echo "yc CLI is required" >&2; exit 1; }
command -v jq >/dev/null || { echo "jq is required" >&2; exit 1; }

echo "LIVE_EVIDENCE_HEAD=${GITHUB_SHA:-unknown}"
yc resource-manager cloud get "$YC_CLOUD_ID" --format=json | jq -e --arg id "$YC_CLOUD_ID" '.id == $id' >/dev/null
yc resource-manager folder get "$YC_FOLDER_ID" --format=json | jq -e --arg id "$YC_FOLDER_ID" '.id == $id' >/dev/null
yc serverless container get "$YC_CONTAINER_NAME" --format=json | jq -e ".status == \"ACTIVE\" or .status == \"RUNNING\"" >/dev/null
yc managed-postgresql cluster get "$YC_CLUSTER_NAME" --format=json | jq -e ".status == \"RUNNING\" or .status == \"ALIVE\"" >/dev/null
yc storage bucket get "$YC_BUCKET_NAME" --format=json >/dev/null
yc billing v1 budget get "$YC_BUDGET_ID" --format=json | jq -e ".status == \"ACTIVE\"" >/dev/null
echo "CLOUD_READY=PASS"
echo "CONTAINER_READY=PASS"
echo "POSTGRES_RESOURCE_READY=PASS"
echo "DATABASE_CONNECTIVITY_AND_MIGRATIONS=NOT_CLAIMED"
echo "BUCKET_READY=PASS"
echo "BUDGET_READY=PASS"
echo "SECRET_VALUES=NOT_PRINTED"
#!/usr/bin/env bash
set -Eeuo pipefail

: "$YC_CLOUD_ID" >/dev/null 2>&1 || { echo "YC_CLOUD_ID is required" >&2; exit 1; }
: "$YC_FOLDER_ID" >/dev/null 2>&1 || { echo "YC_FOLDER_ID is required" >&2; exit 1; }
: "$YC_CONTAINER_NAME" >/dev/null 2>&1 || { echo "YC_CONTAINER_NAME is required" >&2; exit 1; }
: "$YC_API_GATEWAY_ID" >/dev/null 2>&1 || { echo "YC_API_GATEWAY_ID is required" >&2; exit 1; }
: "$YC_MIGRATION_RUNNER_NAME" >/dev/null 2>&1 || { echo "YC_MIGRATION_RUNNER_NAME is required" >&2; exit 1; }
: "$YC_EXPECTED_IMAGE_DIGEST" >/dev/null 2>&1 || { echo "YC_EXPECTED_IMAGE_DIGEST is required" >&2; exit 1; }
: "$YC_CLUSTER_NAME" >/dev/null 2>&1 || { echo "YC_CLUSTER_NAME is required" >&2; exit 1; }
: "$YC_BUCKET_NAME" >/dev/null 2>&1 || { echo "YC_BUCKET_NAME is required" >&2; exit 1; }
: "$YC_BUDGET_ID" >/dev/null 2>&1 || { echo "YC_BUDGET_ID is required" >&2; exit 1; }
: "$YC_TERRAFORM_STATE_BUCKET" >/dev/null 2>&1 || { echo "YC_TERRAFORM_STATE_BUCKET is required" >&2; exit 1; }
: "$AWS_ACCESS_KEY_ID" >/dev/null 2>&1 || { echo "AWS_ACCESS_KEY_ID is required" >&2; exit 1; }
: "$AWS_SECRET_ACCESS_KEY" >/dev/null 2>&1 || { echo "AWS_SECRET_ACCESS_KEY is required" >&2; exit 1; }
: "$YC_RUNTIME_LOG_GROUP_ID" >/dev/null 2>&1 || { echo "YC_RUNTIME_LOG_GROUP_ID is required" >&2; exit 1; }
: "$YC_AUDIT_LOG_GROUP_ID" >/dev/null 2>&1 || { echo "YC_AUDIT_LOG_GROUP_ID is required" >&2; exit 1; }
: "$YC_AUDIT_TRAIL_ID" >/dev/null 2>&1 || { echo "YC_AUDIT_TRAIL_ID is required" >&2; exit 1; }
: "$YC_REGISTRY_SCAN_POLICY_ID" >/dev/null 2>&1 || { echo "YC_REGISTRY_SCAN_POLICY_ID is required" >&2; exit 1; }

for command_name in yc jq curl aws; do
  command -v "$command_name" >/dev/null 2>&1 || { echo "missing required command: $command_name" >&2; exit 1; }
done

bash scripts/yandex_cloud_terraform_state_preflight.sh
echo "TERRAFORM_STATE_BACKEND=PASS"


echo "LIVE_EVIDENCE_HEAD=${GITHUB_SHA:-unknown}"
cloud_json="$(yc resource-manager cloud get "$YC_CLOUD_ID" --format=json)"
folder_json="$(yc resource-manager folder get "$YC_FOLDER_ID" --format=json)"
container_json="$(yc serverless container get "$YC_CONTAINER_NAME" --format=json)"
runner_json="$(yc serverless container get "$YC_MIGRATION_RUNNER_NAME" --format=json)"
cluster_json="$(yc managed-postgresql cluster get "$YC_CLUSTER_NAME" --format=json)"
bucket_json="$(yc storage bucket get "$YC_BUCKET_NAME" --format=json)"
budget_json="$(yc billing v1 budget get "$YC_BUDGET_ID" --format=json)"
gateway_json="$(yc serverless api-gateway get --id "$YC_API_GATEWAY_ID" --format=json)"
runtime_log_group_json="$(yc logging group get --id "$YC_RUNTIME_LOG_GROUP_ID" --format=json)"
audit_log_group_json="$(yc logging group get --id "$YC_AUDIT_LOG_GROUP_ID" --format=json)"
audit_trail_json="$(yc audit-trails trail get --id "$YC_AUDIT_TRAIL_ID" --format=json)"
scan_policy_json="$(yc cloud-registry registry scan-policy get --id "$YC_REGISTRY_SCAN_POLICY_ID" --format=json)"

jq -e --arg id "$YC_CLOUD_ID" '.id == $id' <<<"$cloud_json" >/dev/null
jq -e --arg id "$YC_FOLDER_ID" '.id == $id' <<<"$folder_json" >/dev/null
jq -e '.status == "ACTIVE" or .status == "RUNNING"' <<<"$container_json" >/dev/null
jq -e '.status == "ACTIVE" or .status == "RUNNING"' <<<"$runner_json" >/dev/null
jq -e '.status == "RUNNING" or .status == "ALIVE"' <<<"$cluster_json" >/dev/null
jq -e '.status == "ACTIVE" and (.domain // "") != ""' <<<"$gateway_json" >/dev/null
jq -e '.config.backup_retain_period_days >= 14' <<<"$cluster_json" >/dev/null
jq -e --arg bucket "$YC_BUCKET_NAME" '.name == $bucket or .id == $bucket' <<<"$bucket_json" >/dev/null
jq -e '.status == "ACTIVE"' <<<"$budget_json" >/dev/null
jq -e '((.threshold_rules // .thresholdRules // []) | length) >= 1' <<<"$budget_json" >/dev/null
jq -e '(.retention_period_hours // .retentionPeriodHours // 0) >= 720' <<<"$runtime_log_group_json" >/dev/null
jq -e '(.retention_period_hours // .retentionPeriodHours // 0) >= 720' <<<"$audit_log_group_json" >/dev/null
jq -e '.status == "ACTIVE" or .status == "RUNNING"' <<<"$audit_trail_json" >/dev/null
jq -e '.disabled == false' <<<"$scan_policy_json" >/dev/null
jq -e '(.rules.push_rule.disabled // true) == false' <<<"$scan_policy_json" >/dev/null
jq -e '((.rules.schedule_rules // []) | length) >= 1' <<<"$scan_policy_json" >/dev/null

echo "BACKUP_RETENTION=PASS"
echo "BUDGET_THRESHOLDS=PASS"
echo "API_GATEWAY_READY=PASS"
echo "RUNTIME_LOG_GROUP=PASS"
echo "AUDIT_LOG_GROUP=PASS"
echo "AUDIT_TRAIL=PASS"
echo "REGISTRY_SCAN_POLICY=PASS"

CONTAINER_URL="$(jq -r '.url // empty' <<<"$container_json")"
API_GATEWAY_DOMAIN="$(jq -r '.domain // empty' <<<"$gateway_json")"
API_URL="https://$API_GATEWAY_DOMAIN"
RUNNER_URL="$(jq -r '.url // empty' <<<"$runner_json")"
CONTAINER_ID="$(jq -r '.id // empty' <<<"$container_json")"
RUNNER_ID="$(jq -r '.id' <<<"$runner_json")"
test -n "$CONTAINER_URL" && test -n "$API_GATEWAY_DOMAIN" && test -n "$API_URL" && test -n "$RUNNER_URL" && test -n "$CONTAINER_ID" && test -n "$RUNNER_ID"

echo "CLOUD_READY=PASS"
echo "CONTAINER_READY=PASS"
active_revision_json="$(yc serverless container revision list --container-id "$CONTAINER_ID" --format=json | jq -c '[.[] | select(.status == "ACTIVE")][0] // empty')"
test -n "$active_revision_json"
active_image_digest="$(jq -r '.image.image_digest // empty' <<<"$active_revision_json")"
test "$active_image_digest" = "$YC_EXPECTED_IMAGE_DIGEST"
echo "IMMUTABLE_IMAGE_DIGEST=PASS"
echo "POSTGRES_RESOURCE_READY=PASS"
echo "BUCKET_READY=PASS"
echo "BUDGET_READY=PASS"

health_code="$(curl -sS -o /dev/null -w "%{http_code}" "$API_URL/health/ready")"
[[ "$health_code" == "200" ]] || { echo "health/readiness failed: HTTP $health_code" >&2; exit 1; }
echo "HEALTH_READINESS=PASS"

docs_code="$(curl -sS -o /dev/null -w "%{http_code}" "$API_URL/docs")"
[[ "$docs_code" == "404" ]] || { echo "production docs endpoint unexpectedly exposed: HTTP $docs_code" >&2; exit 1; }
echo "PRODUCTION_DOCS_DISABLED=PASS"

protected_code="$(curl -sS -o /dev/null -w "%{http_code}" "$API_URL/v1/orders/phase7c-smoke-nonexistent")"
[[ "$protected_code" == "401" ]] || { echo "protected route did not fail closed: HTTP $protected_code" >&2; exit 1; }
echo "PROTECTED_ROUTE_FAIL_CLOSED=PASS"
echo "PRODUCTION_SMOKE=PASS"

IAM_TOKEN="$(yc iam create-token)"
headers_file="$(mktemp)"
body_file="$(mktemp)"
trap 'rm -f "$headers_file" "$body_file"' EXIT

curl -sS -D "$headers_file" -o "$body_file" -H "Authorization: Bearer $IAM_TOKEN" "$RUNNER_URL"
task_exit_code="$(awk 'BEGIN{IGNORECASE=1} /^X-Task-Exit-Code:/{gsub("\r","",$2); print $2}' "$headers_file" | tail -n1)"
[[ "$task_exit_code" == "0" ]] || { echo "same-VPC migration task failed with exit code ${task_exit_code:-unknown}" >&2; cat "$body_file" >&2 || true; exit 1; }
echo "DATABASE_CONNECTIVITY_AND_MIGRATIONS=PASS"
echo "LOCKBOX_DATABASE_SECRET_DELIVERY=PASS"

runner_log_probe="$(yc logging read --resource-ids="$RUNNER_ID" --since=10m --limit=20 --format=json)"
jq -e 'length > 0' <<<"$runner_log_probe" >/dev/null
container_log_probe="$(yc logging read --resource-ids="$CONTAINER_ID" --since=10m --limit=20 --format=json)"
jq -e 'length > 0' <<<"$container_log_probe" >/dev/null
echo "OBSERVABILITY_LOG_INGESTION=PASS"
echo "RUNTIME_AND_TASK_LOGGING=PASS"
echo "AUDIT_TRAIL_LIVE=PASS"
echo "REGISTRY_VULNERABILITY_SCAN_POLICY=PASS"

runner_revision="$(jq -r '.revision_id' <<<"$runner_json")"
test -n "$runner_revision"
echo "MIGRATION_RUNNER_REVISION_PRESENT=PASS"
echo "SECRET_VALUES=NOT_PRINTED"

if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  {
    echo "## Phase 7C live evidence"
    echo ""
    echo "- HEAD: ${GITHUB_SHA:-unknown}"
    echo "- Cloud/folder: verified"
    echo "- API Gateway: active and used as the external edge"
    echo "- Serverless Container: active"
    echo "- Immutable image digest: verified"
    echo "- Same-VPC migration task: exit code 0"
    echo "- Managed PostgreSQL: active"
    echo "- Health/readiness: HTTP 200"
    echo "- Production docs: HTTP 404"
    echo "- Protected route: HTTP 401 without credentials"
    echo "- Cloud Logging ingestion: observed"
    echo "- Object Storage bucket: present"
    echo "- Billing budget: active with at least one notification threshold"
    echo "- Runtime/task logs: observed"
    echo "- Runtime log group: verified with 30-day retention"
    echo "- Audit log group and Audit Trail: verified"
    echo "- Container Registry scan policy: push + scheduled scanning enabled"
    echo "- Secret values: intentionally not printed"
  } >> "$GITHUB_STEP_SUMMARY"
fi

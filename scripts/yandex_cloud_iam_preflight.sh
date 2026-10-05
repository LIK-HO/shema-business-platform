#!/usr/bin/env bash
set -Eeuo pipefail

: "${YC_CLOUD_ID:?YC_CLOUD_ID is required}"
: "${YC_FOLDER_ID:?YC_FOLDER_ID is required}"
: "${YC_SERVICE_ACCOUNT_KEY_FILE:?YC_SERVICE_ACCOUNT_KEY_FILE is required}"

command -v yc >/dev/null 2>&1 || { echo "missing required command: yc" >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "missing required command: jq" >&2; exit 1; }

test -r "$YC_SERVICE_ACCOUNT_KEY_FILE" || {
  echo "deployment service-account key file is not readable" >&2
  exit 1
}

service_account_id="$(jq -r '.service_account_id // .serviceAccountId // empty' "$YC_SERVICE_ACCOUNT_KEY_FILE")"
test -n "$service_account_id" || {
  echo "service-account key does not contain service_account_id" >&2
  exit 1
}

folder_bindings="$(yc resource-manager folder list-access-bindings --id "$YC_FOLDER_ID" --format=json)"
cloud_bindings="$(yc resource-manager cloud list-access-bindings --id "$YC_CLOUD_ID" --format=json)"

roles="$(
  jq -r --arg sa "$service_account_id" '
    .[]
    | select(.subject.type == "serviceAccount" and .subject.id == $sa)
    | .role_id
  ' <<<"$folder_bindings"
  jq -r --arg sa "$service_account_id" '
    .[]
    | select(.subject.type == "serviceAccount" and .subject.id == $sa)
    | .role_id
  ' <<<"$cloud_bindings"
)"

roles="$(printf '%s\n' "$roles" | sed '/^$/d' | sort -u)"
role_present() {
  local expected
  for expected in "$@"; do
    if grep -Fxq "$expected" <<<"$roles"; then
      return 0
    fi
  done
  return 1
}

require_role_set() {
  local capability="$1"
  shift
  if role_present "$@"; then
    echo "IAM_${capability}=PASS"
  else
    echo "IAM_${capability}=FAIL"
    echo "IAM_${capability}_REQUIRED=$*"
    return 1
  fi
}

failures=0

require_role_set CONTAINER_REGISTRY container-registry.editor container-registry.admin admin || failures=$((failures + 1))
require_role_set SERVICE_ACCOUNTS iam.serviceAccounts.admin iam.editor iam.admin admin || failures=$((failures + 1))
require_role_set SERVICE_ACCOUNT_USE iam.serviceAccounts.user iam.serviceAccounts.admin iam.editor iam.admin admin || failures=$((failures + 1))
require_role_set VPC_NETWORK vpc.privateAdmin vpc.admin admin || failures=$((failures + 1))
require_role_set VPC_SECURITY_GROUPS vpc.securityGroups.admin vpc.admin admin || failures=$((failures + 1))
require_role_set POSTGRES managed-postgresql.editor managed-postgresql.admin admin || failures=$((failures + 1))
require_role_set LOGGING logging.editor logging.admin admin || failures=$((failures + 1))
require_role_set LOCKBOX_ACCESS lockbox.admin admin || failures=$((failures + 1))
require_role_set AUDIT_TRAILS audit-trails.editor audit-trails.admin admin || failures=$((failures + 1))
require_role_set SERVERLESS_CONTAINERS serverless-containers.editor serverless-containers.admin admin || failures=$((failures + 1))
require_role_set SERVERLESS_CONTAINER_IAM serverless-containers.admin admin || failures=$((failures + 1))
require_role_set API_GATEWAY api-gateway.editor api-gateway.admin admin || failures=$((failures + 1))
require_role_set OBJECT_STORAGE storage.editor admin || failures=$((failures + 1))
require_role_set FOLDER_IAM_MANAGEMENT resource-manager.admin admin resource-manager.clouds.owner || failures=$((failures + 1))

echo "IAM_SERVICE_ACCOUNT_ID=$service_account_id"
echo "IAM_EFFECTIVE_ROLES_BEGIN"
printf '%s\n' "$roles"
echo "IAM_EFFECTIVE_ROLES_END"

if (( failures > 0 )); then
  echo "IAM_PREFLIGHT=FAIL"
  echo "IAM_PREFLIGHT_FAILURES=$failures"
  exit 1
fi

echo "IAM_PREFLIGHT=PASS"

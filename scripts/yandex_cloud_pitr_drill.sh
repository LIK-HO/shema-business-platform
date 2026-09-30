#!/usr/bin/env bash
set -Eeuo pipefail

: "$YC_FOLDER_ID" >/dev/null 2>&1 || { echo "YC_FOLDER_ID is required" >&2; exit 1; }
: "$YC_CLUSTER_NAME" >/dev/null 2>&1 || { echo "YC_CLUSTER_NAME is required" >&2; exit 1; }
: "$YC_MIGRATION_RUNNER_NAME" >/dev/null 2>&1 || { echo "YC_MIGRATION_RUNNER_NAME is required" >&2; exit 1; }
: "$PITR_RECOVERY_TIME" >/dev/null 2>&1 || { echo "PITR_RECOVERY_TIME is required" >&2; exit 1; }
: "$PITR_DATABASE_URL" >/dev/null 2>&1 || { echo "PITR_DATABASE_URL is required" >&2; exit 1; }
: "$PITR_INVOCATION_SERVICE_ACCOUNT_ID" >/dev/null 2>&1 || { echo "PITR_INVOCATION_SERVICE_ACCOUNT_ID is required" >&2; exit 1; }

for command_name in yc jq python curl; do
  command -v "$command_name" >/dev/null 2>&1 || { echo "missing required command: $command_name" >&2; exit 1; }
done

RUN_ID="$GITHUB_RUN_ID"
[[ -n "$RUN_ID" ]] || RUN_ID=manual
RECOVERY_CLUSTER_NAME="shema-pitr-recovery-$RUN_ID"
RECOVERY_RUNNER_NAME="shema-pitr-recovery-runner-$RUN_ID"
RECOVERY_SECRET_NAME="shema-pitr-recovery-$RUN_ID"
RECOVERY_CLUSTER_ID=""
RECOVERY_SECRET_ID=""
RECOVERY_RUNNER_ID=""
HEADERS_FILE="$(mktemp)"
BODY_FILE="$(mktemp)"

cleanup() {
  local rc=$?
  local cleanup_rc=0
  set +e
  rm -f "$HEADERS_FILE" "$BODY_FILE"

  if [[ -n "$RECOVERY_RUNNER_ID" ]]; then
    yc serverless container delete --id "$RECOVERY_RUNNER_ID" >/dev/null 2>&1 || cleanup_rc=1
    for _ in $(seq 1 30); do
      if yc serverless container get --id "$RECOVERY_RUNNER_ID" >/dev/null 2>&1; then sleep 2; else break; fi
    done
    yc serverless container get --id "$RECOVERY_RUNNER_ID" >/dev/null 2>&1 && cleanup_rc=1
  fi

  if [[ -n "$RECOVERY_SECRET_ID" ]]; then
    printf 'yes\n' | yc lockbox secret delete --id "$RECOVERY_SECRET_ID" >/dev/null 2>&1 || cleanup_rc=1
    for _ in $(seq 1 30); do
      if yc lockbox secret get "$RECOVERY_SECRET_ID" >/dev/null 2>&1; then sleep 2; else break; fi
    done
    yc lockbox secret get "$RECOVERY_SECRET_ID" >/dev/null 2>&1 && cleanup_rc=1
  fi

  if [[ -n "$RECOVERY_CLUSTER_ID" ]]; then
    printf 'yes\n' | yc managed-postgresql cluster delete "$RECOVERY_CLUSTER_ID" >/dev/null 2>&1 || cleanup_rc=1
    for _ in $(seq 1 60); do
      if yc managed-postgresql cluster get "$RECOVERY_CLUSTER_ID" --folder-id "$YC_FOLDER_ID" >/dev/null 2>&1; then sleep 5; else break; fi
    done
    yc managed-postgresql cluster get "$RECOVERY_CLUSTER_ID" --folder-id "$YC_FOLDER_ID" >/dev/null 2>&1 && cleanup_rc=1
  fi

  if [[ "$cleanup_rc" -eq 0 ]]; then
    echo "PITR_RECOVERY_CLEANUP=PASS"
  else
    echo "PITR_RECOVERY_CLEANUP=FAIL" >&2
    rc=1
  fi

  trap - EXIT
  exit "$rc"
}
trap cleanup EXIT

source_cluster_json="$(yc managed-postgresql cluster get "$YC_CLUSTER_NAME" --folder-id "$YC_FOLDER_ID" --format=json)"
SOURCE_CLUSTER_ID="$(jq -r '.id // empty' <<<"$source_cluster_json")"
NETWORK_ID="$(jq -r '.network_id // empty' <<<"$source_cluster_json")"
PG_VERSION="$(jq -r '.config.version // .config.postgresql_version // "17"' <<<"$source_cluster_json")"
RESOURCE_PRESET="$(jq -r '.config.resources.resource_preset_id // .config.resources[0].resource_preset_id // "s2.micro"' <<<"$source_cluster_json")"
DISK_TYPE="$(jq -r '.config.resources.disk_type_id // .config.resources[0].disk_type_id // "network-ssd"' <<<"$source_cluster_json")"
DISK_BYTES="$(jq -r '.config.resources.disk_size // .config.resources[0].disk_size // empty' <<<"$source_cluster_json")"
SECURITY_GROUP_IDS="$(jq -r '(.security_group_ids // []) | join(",")' <<<"$source_cluster_json")"
test -n "$SOURCE_CLUSTER_ID" && test -n "$NETWORK_ID" && test -n "$DISK_BYTES"

DISK_SIZE_GB="$(python - "$DISK_BYTES" <<'PY'
import math
import sys
print(max(1, math.ceil(int(sys.argv[1]) / (1024 ** 3))))
PY
)"

hosts_json="$(yc managed-postgresql hosts list --cluster-id "$SOURCE_CLUSTER_ID" --folder-id "$YC_FOLDER_ID" --format=json)"
ZONE_ID="$(jq -r '[.[] | select(.role == "MASTER" and .health == "ALIVE")][0].zone_id // empty' <<<"$hosts_json")"
SUBNET_ID="$(jq -r '[.[] | select(.role == "MASTER" and .health == "ALIVE")][0].subnet_id // empty' <<<"$hosts_json")"
test -n "$ZONE_ID" && test -n "$SUBNET_ID"

backups_json="$(yc managed-postgresql backup list --folder-id "$YC_FOLDER_ID" --format=json)"
backup_record="$(python - "$backups_json" "$SOURCE_CLUSTER_ID" "$PITR_RECOVERY_TIME" <<'PY'
import json
import sys
from datetime import datetime, timezone
items = json.loads(sys.argv[1])
cluster_id = sys.argv[2]
target = datetime.fromisoformat(sys.argv[3].replace("Z", "+00:00"))
if target.tzinfo is None:
    target = target.replace(tzinfo=timezone.utc)
target = target.astimezone(timezone.utc)
eligible = []
for item in items:
    if item.get("source_cluster_id") != cluster_id or not item.get("created_at"):
        continue
    created = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")).astimezone(timezone.utc)
    if created <= target:
        eligible.append((created, item))
if not eligible:
    raise SystemExit("no backup exists at or before requested PITR recovery time")
selected = sorted(eligible, key=lambda pair: pair[0])[-1][1]
print(json.dumps({"id": selected.get("id", ""), "created_at": selected.get("created_at", "")}))
PY
)"
BACKUP_ID="$(jq -r '.id // empty' <<<"$backup_record")"
BACKUP_CREATED_AT="$(jq -r '.created_at // empty' <<<"$backup_record")"
test -n "$BACKUP_ID" && test -n "$BACKUP_CREATED_AT"

python - "$BACKUP_CREATED_AT" "$PITR_RECOVERY_TIME" <<'PY'
import sys
from datetime import datetime, timezone
created = datetime.fromisoformat(sys.argv[1].replace("Z", "+00:00")).astimezone(timezone.utc)
target = datetime.fromisoformat(sys.argv[2].replace("Z", "+00:00"))
if target.tzinfo is None:
    target = target.replace(tzinfo=timezone.utc)
target = target.astimezone(timezone.utc)
if target <= created:
    raise SystemExit("PITR_RECOVERY_TIME must be after selected backup completion time")
if target > datetime.now(timezone.utc):
    raise SystemExit("PITR_RECOVERY_TIME must not be in the future")
PY

restore_command=(
  yc managed-postgresql cluster restore
  --backup-id "$BACKUP_ID"
  --time "$PITR_RECOVERY_TIME"
  --name "$RECOVERY_CLUSTER_NAME"
  --description "Temporary protected PITR recovery drill; delete after verification."
  --environment PRESTABLE
  --folder-id "$YC_FOLDER_ID"
  --network-id "$NETWORK_ID"
  --host "zone-id=$ZONE_ID,subnet-id=$SUBNET_ID,assign-public-ip=false"
  --postgresql-version "$PG_VERSION"
  --resource-preset "$RESOURCE_PRESET"
  --disk-size "$DISK_SIZE_GB"GB
  --disk-type "$DISK_TYPE"
  --labels "project=shema,purpose=pitr-recovery"
)
if [[ -n "$SECURITY_GROUP_IDS" ]]; then
  restore_command+=(--security-group-ids "$SECURITY_GROUP_IDS")
fi
"${restore_command[@]}" >/dev/null

for _ in $(seq 1 120); do
  recovery_info="$(yc managed-postgresql cluster get "$RECOVERY_CLUSTER_NAME" --folder-id "$YC_FOLDER_ID" --format=json)"
  RECOVERY_CLUSTER_ID="$(jq -r '.id // empty' <<<"$recovery_info")"
  recovery_status="$(jq -r '.status // empty' <<<"$recovery_info")"
  case "$recovery_status" in
    RUNNING|ALIVE|ACTIVE) break ;;
    ERROR|FAILED) echo "recovery cluster entered terminal failure state" >&2; exit 1 ;;
  esac
  sleep 10
done

test -n "$RECOVERY_CLUSTER_ID"
case "$(yc managed-postgresql cluster get "$RECOVERY_CLUSTER_ID" --folder-id "$YC_FOLDER_ID" --format=json | jq -r '.status // empty')" in
  RUNNING|ALIVE|ACTIVE) ;;
  *) echo "recovery cluster did not reach a ready state" >&2; exit 1 ;;
esac

jq -e --arg network "$NETWORK_ID" '.network_id == $network' <<<"$recovery_info" >/dev/null
recovery_hosts="$(yc managed-postgresql hosts list --cluster-id "$RECOVERY_CLUSTER_ID" --folder-id "$YC_FOLDER_ID" --format=json)"
jq -e 'length > 0 and all(.[]; (.assign_public_ip // false) == false)' <<<"$recovery_hosts" >/dev/null

echo "PITR_BACKUP_SELECTED=PASS"
echo "PITR_RECOVERY_CLUSTER_READY=PASS"
echo "PITR_RECOVERY_SAME_VPC=PASS"
echo "PITR_RECOVERY_NO_PUBLIC_IP=PASS"

RECOVERY_MASTER_HOST="c-$RECOVERY_CLUSTER_ID.rw.mdb.yandexcloud.net"
RECOVERY_DATABASE_URL="$(python - "$PITR_DATABASE_URL" "$RECOVERY_MASTER_HOST" <<'PY'
import sys
from urllib.parse import urlsplit, urlunsplit
source = sys.argv[1]
new_host = sys.argv[2]
parts = urlsplit(source)
if not parts.scheme or not parts.hostname:
    raise SystemExit("PITR_DATABASE_URL must be a PostgreSQL URI")
netloc = parts.netloc.replace(parts.hostname, new_host, 1)
print(urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment)))
PY
)"
test -n "$RECOVERY_DATABASE_URL"

payload="$(jq -cn --arg value "$RECOVERY_DATABASE_URL" '[{"key":"DATABASE_URL","text_value":$value}]')"
secret_json="$(printf '%s' "$payload" | yc lockbox secret create --name "$RECOVERY_SECRET_NAME" --description "Ephemeral PITR drill database credential. Deleted by cleanup." --labels "project=shema,purpose=pitr-recovery" --payload - --folder-id "$YC_FOLDER_ID" --format=json)"
RECOVERY_SECRET_ID="$(jq -r '.id // empty' <<<"$secret_json")"
test -n "$RECOVERY_SECRET_ID"
RECOVERY_SECRET_VERSION_ID="$(yc lockbox secret get "$RECOVERY_SECRET_ID" --format=json | jq -r '.current_version_id // empty')"
test -n "$RECOVERY_SECRET_VERSION_ID"

runner_json="$(yc serverless container get "$YC_MIGRATION_RUNNER_NAME" --format=json)"
RUNNER_SERVICE_ACCOUNT_ID="$(jq -r '.service_account_id // empty' <<<"$runner_json")"
RUNNER_REVISION_ID="$(jq -r '.latest_revision.id // .revision_id // empty' <<<"$runner_json")"
test -n "$RUNNER_SERVICE_ACCOUNT_ID" && test -n "$RUNNER_REVISION_ID"
runner_revision_json="$(yc serverless container revision get "$RUNNER_REVISION_ID" --format=json)"
IMAGE_URL="$(jq -r '.image.image_url // empty' <<<"$runner_revision_json")"
IMAGE_DIGEST="$(jq -r '.image.image_digest // empty' <<<"$runner_revision_json")"
test -n "$IMAGE_URL" && test -n "$IMAGE_DIGEST"

yc lockbox secret add-access-binding --id "$RECOVERY_SECRET_ID" --role lockbox.payloadViewer --subject "serviceAccount:$RUNNER_SERVICE_ACCOUNT_ID" >/dev/null

runner_create_json="$(yc serverless container create --name "$RECOVERY_RUNNER_NAME" --description "Ephemeral same-VPC task runner for PITR verification." --labels "project=shema,purpose=pitr-recovery" --folder-id "$YC_FOLDER_ID" --format=json)"
RECOVERY_RUNNER_ID="$(jq -r '.id // empty' <<<"$runner_create_json")"
test -n "$RECOVERY_RUNNER_ID"
yc serverless container add-access-binding --id "$RECOVERY_RUNNER_ID" --role serverless-containers.containerInvoker --subject "serviceAccount:$PITR_INVOCATION_SERVICE_ACCOUNT_ID" >/dev/null

revision_json="$(yc serverless container revision deploy \
  --container-id "$RECOVERY_RUNNER_ID" \
  --memory 512MB --cores 1 --core-fraction 100 --execution-timeout 120s --concurrency 1 \
  --service-account-id "$RUNNER_SERVICE_ACCOUNT_ID" \
  --image "$IMAGE_URL@$IMAGE_DIGEST" \
  --command python,-m,shema_platform.platform.live_migration_probe \
  --runtime task --network-id "$NETWORK_ID" \
  --environment APP_ENV=pitr_recovery \
  --secret "environment-variable=DATABASE_URL,id=$RECOVERY_SECRET_ID,version-id=$RECOVERY_SECRET_VERSION_ID,key=DATABASE_URL" \
  --format=json)"
RECOVERY_RUNNER_REVISION_ID="$(jq -r '.id // empty' <<<"$revision_json")"
test -n "$RECOVERY_RUNNER_REVISION_ID"

runner_url="$(jq -r '.url // empty' <<<"$runner_create_json")"
test -n "$runner_url"
iam_token="$(yc iam create-token)"
curl -sS -D "$HEADERS_FILE" -o "$BODY_FILE" -H "Authorization: Bearer $iam_token" "$runner_url"

task_exit_code="$(awk 'BEGIN{IGNORECASE=1} /^X-Task-Exit-Code:/{gsub("\\r","",$2); print $2}' "$HEADERS_FILE" | tail -n1)"
[[ "$task_exit_code" == "0" ]] || { echo "recovery verification task failed with exit code $task_exit_code" >&2; exit 1; }

echo "PITR_RECOVERY_DATABASE_CONNECTIVITY=PASS"
echo "PITR_RECOVERY_MIGRATIONS=PASS"
echo "PITR_RECOVERY_VERIFICATION_TASK=PASS"
echo "PITR_PRODUCTION_MUTATION=NONE"
echo "SECRET_VALUES=NOT_PRINTED"

if [[ -n "$GITHUB_STEP_SUMMARY" ]]; then
  {
    echo "## Phase 7C PITR recovery drill"
    echo "- Separate PRESTABLE recovery cluster"
    echo "- Selected automated backup and operator-supplied recovery time"
    echo "- Same VPC; no public database IP"
    echo "- Same-VPC verification task exit code 0"
    echo "- Production mutation: none"
  } >> "$GITHUB_STEP_SUMMARY"
fi

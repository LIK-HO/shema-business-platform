#!/usr/bin/env bash
set -Eeuo pipefail

: "${YC_CONTAINER_NAME:?YC_CONTAINER_NAME is required}"
: "${PREVIOUS_REVISION_ID:?PREVIOUS_REVISION_ID is required}"
command -v yc >/dev/null 2>&1 || { echo "yc CLI is required" >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "jq is required" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "curl is required" >&2; exit 1; }

API_URL="$(yc serverless container get "$YC_CONTAINER_NAME" --format=json | jq -r ".url // empty")"
test -n "$API_URL" || { echo "cannot determine container URL" >&2; exit 1; }

active_revision() {
  yc serverless container revision list --container-name "$YC_CONTAINER_NAME" --format=json |
    jq -r '[.[] | select(.status == "ACTIVE") | .id][0] // empty'
}

wait_for_active_revision() {
  local expected="$1"
  for _ in {1..60}; do
    if [[ "$(active_revision)" == "$expected" ]]; then
      return 0
    fi
    sleep 2
  done
  echo "active revision did not converge to $expected" >&2
  return 1
}

NEW_REVISION_ID="$(active_revision)"
test -n "$NEW_REVISION_ID" || { echo "cannot determine active revision before rollback drill" >&2; exit 1; }
[[ "$NEW_REVISION_ID" != "$PREVIOUS_REVISION_ID" ]] || { echo "previous and current revisions are identical; rollback drill is not meaningful" >&2; exit 1; }

yc serverless container revision get "$PREVIOUS_REVISION_ID" --format=json |
  jq -e --arg revision "$PREVIOUS_REVISION_ID" '.id == $revision and .image.image_digest != null' >/dev/null
yc serverless container revision get "$NEW_REVISION_ID" --format=json |
  jq -e --arg revision "$NEW_REVISION_ID" '.id == $revision and .image.image_digest != null' >/dev/null

yc serverless container rollback --name "$YC_CONTAINER_NAME" --revision-id "$PREVIOUS_REVISION_ID" >/dev/null
wait_for_active_revision "$PREVIOUS_REVISION_ID"

previous_health="$(curl -sS -o /dev/null -w "%{http_code}" "$API_URL/health/ready")"
[[ "$previous_health" == "200" ]] || { echo "rollback target health failed: HTTP $previous_health" >&2; exit 1; }
echo "ROLLBACK_TO_PREVIOUS=PASS"

yc serverless container rollback --name "$YC_CONTAINER_NAME" --revision-id "$NEW_REVISION_ID" >/dev/null
wait_for_active_revision "$NEW_REVISION_ID"

restored_health="$(curl -sS -o /dev/null -w "%{http_code}" "$API_URL/health/ready")"
[[ "$restored_health" == "200" ]] || { echo "restored revision health failed: HTTP $restored_health" >&2; exit 1; }
echo "ROLLBACK_RESTORE_CURRENT=PASS"
echo "ROLLBACK_EVIDENCE=PASS"
echo "SECRET_VALUES=NOT_PRINTED"

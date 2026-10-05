#!/usr/bin/env bash
set -Eeuo pipefail

: "${YC_REGISTRY_ID:?YC_REGISTRY_ID is required}"
: "${YC_PULLER_SERVICE_ACCOUNT_IDS:?YC_PULLER_SERVICE_ACCOUNT_IDS is required}"

for command_name in yc jq; do
  command -v "$command_name" >/dev/null 2>&1 || {
    echo "missing required command: $command_name" >&2
    exit 1
  }
done

role="container-registry.images.puller"
bindings_json="$(yc container registry list-access-bindings "$YC_REGISTRY_ID" --format=json)"

has_binding() {
  local service_account_id="$1"
  jq -e --arg role "$role" --arg sid "$service_account_id" '
    (if type == "object"
      then (.accessBindings // .access_bindings // [])
      else .
    end)[]?
    | select(
        (.roleId // .role_id) == $role
        and ((.subject.type // "") == "serviceAccount" or (.subject.type // "") == "service_account")
        and (.subject.id // "") == $sid
      )
  ' <<<"$bindings_json" >/dev/null
}

for service_account_id in $YC_PULLER_SERVICE_ACCOUNT_IDS; do
  [[ -n "$service_account_id" ]] || continue
  if has_binding "$service_account_id"; then
    continue
  fi

  last_error=""
  for _ in 1 2 3 4 5; do
    set +e
    output="$(yc container registry add-access-binding "$YC_REGISTRY_ID"       --role "$role"       --subject "serviceAccount:$service_account_id" 2>&1)"
    rc=$?
    set -e
    if (( rc == 0 )); then
      last_error=""
      break
    fi
    last_error="$output"
    sleep 5
  done

  if [[ -n "$last_error" ]]; then
    echo "Container Registry pull binding failed for service account $service_account_id." >&2
    echo "$last_error" >&2
    exit 1
  fi
done

bindings_json="$(yc container registry list-access-bindings "$YC_REGISTRY_ID" --format=json)"
for service_account_id in $YC_PULLER_SERVICE_ACCOUNT_IDS; do
  has_binding "$service_account_id" || {
    echo "Container Registry pull binding was not verified for service account $service_account_id." >&2
    exit 1
  }
done

echo "CONTAINER_REGISTRY_PULL_ACCESS=PASS"

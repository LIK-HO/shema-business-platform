#!/usr/bin/env bash
set -Eeuo pipefail

: "${YC_REGISTRY_ID:?YC_REGISTRY_ID is required}"
: "${APP_NAME:?APP_NAME is required}"

MODE="${1:-ensure}"
case "$MODE" in
  ensure|verify) ;;
  *)
    echo "usage: $0 <ensure|verify>" >&2
    exit 2
    ;;
esac

for command_name in yc jq curl; do
  command -v "$command_name" >/dev/null 2>&1 || {
    echo "missing required command: $command_name" >&2
    exit 1
  }
done

YC_PRIMARY_PROFILE="${YC_PRIMARY_PROFILE:-shema-phase7c}"
IAM_TOKEN="$(timeout 45s yc --profile="$YC_PRIMARY_PROFILE" iam create-token)"
test -n "$IAM_TOKEN"
jwt_workdir="$(mktemp -d)"
trap "rm -rf \"$jwt_workdir\"" EXIT

if [[ -n "${YC_REGISTRY_IAM_TOKEN_FILE:-}" ]]; then
  umask 077
  printf "%s" "$IAM_TOKEN" > "$YC_REGISTRY_IAM_TOKEN_FILE"
fi

API_BASE="https://container-registry.api.cloud.yandex.net/container-registry/v1"
OPERATION_BASE="https://operation.api.cloud.yandex.net/operations"
policy_name="${APP_NAME}-image-scan"
policy_description="Production vulnerability scanning on push plus daily rescan."

desired_policy="$(jq -n   --arg registry_id "$YC_REGISTRY_ID"   --arg name "$policy_name"   --arg description "$policy_description"   '{
    registryId: $registry_id,
    name: $name,
    description: $description,
    rules: {
      pushRule: {
        repositoryPrefixes: ["*"],
        disabled: false
      },
      scheduleRules: [
        {
          repositoryPrefixes: ["*"],
          rescanPeriod: "86400s",
          disabled: false
        }
      ]
    }
  }')"

curl_json() {
  local method="$1"
  local url="$2"
  local body="$3"
  local out="$4"
  local code
  for attempt in 1 2 3; do
    code="$(curl -sS --connect-timeout 15 --max-time 60       -o "$out" -w "%{http_code}"       -X "$method"       -H "Authorization: Bearer $IAM_TOKEN"       -H "Content-Type: application/json"       -H "Accept: application/json"       ${body:+-d "$body"}       "$url")" && {
        printf '%s' "$code"
        return 0
      }
    sleep $((attempt * 2))
  done
  return 1
}

get_policy() {
  local output_file="$1"
  local http_code
  if ! http_code="$(curl_json GET       "$API_BASE/scanPolicies/$YC_REGISTRY_ID:byRegistry"       ""       "$output_file")"; then
    echo "Container Registry scan policy lookup failed at transport layer." >&2
    cat "$output_file" >&2 || true
    return 1
  fi
  if [[ "$http_code" == "200" ]]; then
    echo "200"
    return 0
  fi
  if grep -qiE       'Scan policy not found for registry|scanPolicyForRegistryNotFoundException'       "$output_file"; then
    echo "404"
    return 0
  fi
  echo "$http_code"
}

poll_operation() {
  local operation_id="$1"
  local operation_json
  local done
  for _ in $(seq 1 60); do
    operation_json="$(curl -sS --connect-timeout 15 --max-time 30       -H "Authorization: Bearer $IAM_TOKEN"       -H "Accept: application/json"       "$OPERATION_BASE/$operation_id")"
    done="$(jq -r '.done // false' <<<"$operation_json")"
    if [[ "$done" == "true" ]]; then
      if jq -e '.error' <<<"$operation_json" >/dev/null; then
        jq -r '.error.message // "Container Registry scan policy operation failed."' <<<"$operation_json" >&2
        return 1
      fi
      return 0
    fi
    sleep 2
  done
  echo "Container Registry scan policy operation timed out." >&2
  return 1
}

apply_policy() {
  local method="$1"
  local url="$2"
  local body="$3"
  local response_file="$jwt_workdir/operation.json"
  local http_code
  if ! http_code="$(curl_json "$method" "$url" "$body" "$response_file")"; then
    echo "Container Registry scan policy request failed at transport layer." >&2
    cat "$response_file" >&2 || true
    exit 1
  fi
  case "$http_code" in
    200)
      ;;
    *)
      echo "Container Registry scan policy API returned HTTP $http_code." >&2
      jq -r '.message // .error.message // "Scan policy API request failed."'         "$response_file" >&2 || true
      exit 1
      ;;
  esac
  local operation_id
  operation_id="$(jq -r '.id // empty' "$response_file")"
  if [[ -z "$operation_id" ]]; then
    echo "Container Registry scan policy API response did not contain operation id." >&2
    cat "$response_file" >&2 || true
    exit 1
  fi
  poll_operation "$operation_id"
}

tmp_policy="$jwt_workdir/policy.json"
http_code="$(get_policy "$tmp_policy")"
case "$http_code" in
  200)
    policy_json="$(cat "$tmp_policy")"
    ;;
  404)
    policy_json=""
    ;;
  *)
    echo "Container Registry scan policy lookup failed with HTTP $http_code." >&2
    cat "$tmp_policy" >&2 || true
    exit 1
    ;;
esac

policy_matches() {
  [[ -n "$policy_json" ]] || return 1
  jq -e '
    (.registryId // .registry_id) == $registry
    and (.disabled // false) == false
    and ((.rules.pushRule // .rules.push_rule).disabled // true) == false
    and (
      (((.rules.pushRule // .rules.push_rule).repositoryPrefixes
        // (.rules.push_rule.repository_prefixes // []))
        | index("*")) != null
    )
    and (((.rules.scheduleRules // .rules.schedule_rules // []) | length) >= 1)
    and ((((.rules.scheduleRules // .rules.schedule_rules // [])[0]).disabled // false) == false)
    and (
      (((.rules.scheduleRules // .rules.schedule_rules // [])[0]).repositoryPrefixes
        // ((.rules.schedule_rules // [])[0].repository_prefixes // []))
      | index("*")
    ) != null
    and (
      (((.rules.scheduleRules // .rules.schedule_rules // [])[0]).rescanPeriod
        // ((.rules.schedule_rules // [])[0].rescan_period // ""))
      == "86400s"
    )
  ' --arg registry "$YC_REGISTRY_ID" <<<"$policy_json" >/dev/null
}

if ! policy_matches; then
  [[ "$MODE" == "ensure" ]] || {
    echo "Container Registry scan policy is missing or does not match the production contract." >&2
    exit 1
  }

  if [[ -z "$policy_json" ]]; then
    apply_policy POST "$API_BASE/scanPolicies" "$desired_policy"
  else
    policy_id="$(jq -r '.id // empty' <<<"$policy_json")"
    test -n "$policy_id"
    update_body="$(jq -n       --arg name "$policy_name"       --arg description "$policy_description"       --argjson rules "$(jq '.rules' <<<"$desired_policy")"       '{
        updateMask: "name,description,rules",
        name: $name,
        description: $description,
        rules: $rules
      }')"
    apply_policy PATCH "$API_BASE/scanPolicies/$policy_id" "$update_body"
  fi

  http_code="$(get_policy "$tmp_policy")"
  [[ "$http_code" == "200" ]] || {
    echo "Container Registry scan policy was not readable after convergence." >&2
    cat "$tmp_policy" >&2 || true
    exit 1
  }
  policy_json="$(cat "$tmp_policy")"
  policy_matches
fi

policy_id="$(jq -r '.id // empty' <<<"$policy_json")"
test -n "$policy_id"
echo "REGISTRY_SCAN_POLICY_ID=$policy_id"
echo "REGISTRY_SCAN_POLICY=PASS"

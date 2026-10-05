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

API_BASE="https://container-registry.api.cloud.yandex.net/container-registry/v1"
OPERATION_BASE="https://operation.api.cloud.yandex.net/operations"
IAM_PROFILE="${YC_IAM_PROFILE:-shema-phase7c}"
IAM_TOKEN=""
for attempt in 1 2 3 4; do
  set +e
  token_output="$(timeout 30s yc iam create-token     --profile "$IAM_PROFILE"     --endpoint iam.api.cloud.yandex.net 2>&1)"
  token_rc=$?
  set -e
  if (( token_rc == 0 )) && [[ -n "$token_output" ]]; then
    IAM_TOKEN="$token_output"
    break
  fi
  if (( attempt < 4 )); then
    sleep 5
  fi
done
if [[ -z "$IAM_TOKEN" ]]; then
  echo "Container Registry scan policy could not obtain an IAM token from iam.api.cloud.yandex.net after 4 attempts." >&2
  exit 1
fi

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

get_policy() {
  local output_file="$1"
  local http_code
  http_code="$(curl -sS --connect-timeout 15 --max-time 30 -o "$output_file" -w "%{http_code}"     -H "Authorization: Bearer $IAM_TOKEN"     -H "Accept: application/json"     "$API_BASE/scanPolicies/$YC_REGISTRY_ID:byRegistry")"
  if [[ "$http_code" == "400" ]] && grep -qiE     'Scan policy not found for registry|scanPolicyForRegistryNotFoundException'     "$output_file"; then
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
  local response
  local operation_id

  response="$(curl -sS --connect-timeout 15 --max-time 30 -X "$method"     -H "Authorization: Bearer $IAM_TOKEN"     -H "Content-Type: application/json"     -H "Accept: application/json"     -d "$body"     "$url")"

  operation_id="$(jq -r '.id // empty' <<<"$response")"
  if [[ -z "$operation_id" ]]; then
    echo "Container Registry scan policy API returned no operation id." >&2
    jq -r '.message // .error.message // "No operation id in API response."' <<<"$response" >&2 || true
    exit 1
  fi
  poll_operation "$operation_id"
}

tmp_policy="$(mktemp)"
trap 'rm -f "$tmp_policy"' EXIT

http_code="$(get_policy "$tmp_policy")"
case "$http_code" in
  200)
    policy_json="$(cat "$tmp_policy")"
    policy_id="$(jq -r '.id // empty' <<<"$policy_json")"
    test -n "$policy_id"
    ;;
  404)
    policy_json=""
    policy_id=""
    ;;
  *)
    echo "Container Registry scan policy lookup failed with HTTP $http_code." >&2
    cat "$tmp_policy" >&2 || true
    exit 1
    ;;
esac

policy_matches() {
  [[ "$policy_json" != "" ]] || return 1
  jq -e '
    def push_rule:
      (.rules.pushRule // .rules.push_rule // {});
    def schedule_rules:
      (.rules.scheduleRules // .rules.schedule_rules // []);
    def schedule0:
      (schedule_rules[0] // {});

    (.registryId // .registry_id) == $registry
    and (.disabled // false) == false
    and (push_rule.disabled == false)
    and (
      (
        push_rule.repositoryPrefixes
        // push_rule.repository_prefixes
        // []
      )
      | index("*")
    ) != null
    and (schedule_rules | length) >= 1
    and (schedule0.disabled == false)
    and (
      (
        schedule0.repositoryPrefixes
        // schedule0.repository_prefixes
        // []
      )
      | index("*")
    ) != null
    and (schedule0.rescanPeriod // schedule0.rescan_period // "") == "86400s"
  ' --arg registry "$YC_REGISTRY_ID" <<<"$policy_json" >/dev/null
}

if ! policy_matches; then
  [[ "$MODE" == "ensure" ]] || {
    echo "Container Registry scan policy is missing or does not match the production contract." >&2
    exit 1
  }

  if [[ -z "$policy_id" ]]; then
    apply_policy POST "$API_BASE/scanPolicies" "$desired_policy"
  else
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
  policy_id="$(jq -r '.id // empty' <<<"$policy_json")"
  test -n "$policy_id"
  policy_matches
fi

echo "REGISTRY_SCAN_POLICY_ID=$policy_id"
echo "REGISTRY_SCAN_POLICY=PASS"

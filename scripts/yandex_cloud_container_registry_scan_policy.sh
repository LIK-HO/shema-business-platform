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

API_BASE="https://registry.api.cloud.yandex.net/cloud-registry/v1"
OPERATION_BASE="https://operation.api.cloud.yandex.net/operations"
IAM_TOKEN="$(yc iam create-token)"
test -n "$IAM_TOKEN"

policy_name="${APP_NAME}-image-scan"
policy_description="Production vulnerability scanning on push plus daily rescan."
desired_policy="$(jq -n   --arg registry_id "$YC_REGISTRY_ID"   --arg name "$policy_name"   --arg description "$policy_description"   '{
    registryId: $registry_id,
    name: $name,
    description: $description,
    scanLangPackages: false,
    rules: {
      pushRule: {
        paths: ["*"],
        disabled: false
      },
      scheduleRules: [
        {
          amount: "1",
          intervalUnit: "DAYS",
          paths: ["*"],
          disabled: false
        }
      ]
    },
    disabled: false
  }')"

get_policy() {
  local output_file="$1"
  curl -sS -o "$output_file" -w "%{http_code}"     -H "Authorization: Bearer $IAM_TOKEN"     -H "Accept: application/json"     "$API_BASE/registries/$YC_REGISTRY_ID/scanPolicy"
}

poll_operation() {
  local operation_id="$1"
  local operation_json
  local done
  for _ in $(seq 1 60); do
    operation_json="$(curl -sS       -H "Authorization: Bearer $IAM_TOKEN"       -H "Accept: application/json"       "$OPERATION_BASE/$operation_id")"
    done="$(jq -r '.done // false' <<<"$operation_json")"
    if [[ "$done" == "true" ]]; then
      if jq -e '.error' <<<"$operation_json" >/dev/null; then
        jq -r '.error.message // "Cloud Registry scan policy operation failed."' <<<"$operation_json" >&2
        return 1
      fi
      return 0
    fi
    sleep 2
  done
  echo "Cloud Registry scan policy operation timed out." >&2
  return 1
}

apply_policy() {
  local method="$1"
  local url="$2"
  local body="$3"
  local response
  local operation_id

  response="$(curl -sS -X "$method"     -H "Authorization: Bearer $IAM_TOKEN"     -H "Content-Type: application/json"     -H "Accept: application/json"     -d "$body"     "$url")"

  operation_id="$(jq -r '.id // empty' <<<"$response")"
  if [[ -z "$operation_id" ]]; then
    echo "Cloud Registry scan policy API returned no operation id." >&2
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
    echo "Cloud Registry scan policy lookup failed with HTTP $http_code." >&2
    cat "$tmp_policy" >&2 || true
    exit 1
    ;;
esac

policy_matches() {
  [[ "$policy_json" != "" ]] || return 1
  jq -e '
    (.registryId // .registry_id) == $registry
    and (.disabled // false) == false
    and ((.rules.pushRule // .rules.push_rule).disabled // true) == false
    and (
      (((.rules.pushRule // .rules.push_rule).paths
        // (.rules.push_rule.paths // []))
        | index("*")) != null
    )
    and (
      (((.rules.scheduleRules // .rules.schedule_rules // [])) | length) >= 1
    )
    and (
      ((((.rules.scheduleRules // .rules.schedule_rules // [])[0]).disabled // false) == false)
    )
    and (
      ((((.rules.scheduleRules // .rules.schedule_rules // [])[0]).amount // "") | tostring) == "1"
    )
    and (
      ((((.rules.scheduleRules // .rules.schedule_rules // [])[0]).intervalUnit
        // ( .rules.schedule_rules // [])[0].interval_unit
        // "") == "DAYS")
    )
    and (
      ((.scanLangPackages // .scanPolicyOptions.scanLangPackages // false) == false)
    )
  ' --arg registry "$YC_REGISTRY_ID" <<<"$policy_json" >/dev/null
}

if ! policy_matches; then
  [[ "$MODE" == "ensure" ]] || {
    echo "Cloud Registry scan policy is missing or does not match the production contract." >&2
    exit 1
  }

  if [[ -z "$policy_id" ]]; then
    apply_policy POST "$API_BASE/scanPolicies" "$desired_policy"
  else
    update_body="$(jq -n       --arg name "$policy_name"       --arg description "$policy_description"       --argjson rules "$(jq '.rules' <<<"$desired_policy")"       '{
        updateMask: "name,description,scanLangPackages,rules,disabled",
        name: $name,
        description: $description,
        scanLangPackages: false,
        rules: $rules,
        disabled: false
      }')"
    apply_policy PATCH "$API_BASE/scanPolicies/$policy_id" "$update_body"
  fi

  http_code="$(get_policy "$tmp_policy")"
  [[ "$http_code" == "200" ]] || {
    echo "Cloud Registry scan policy was not readable after convergence." >&2
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

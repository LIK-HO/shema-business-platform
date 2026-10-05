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
: "${YC_SERVICE_ACCOUNT_KEY_FILE:?YC_SERVICE_ACCOUNT_KEY_FILE is required}"
test -r "$YC_SERVICE_ACCOUNT_KEY_FILE"

for command_name in openssl python3; do
  command -v "$command_name" >/dev/null 2>&1 || {
    echo "missing required command: $command_name" >&2
    exit 1
  }
done

service_account_id="$(jq -r '.service_account_id // empty' "$YC_SERVICE_ACCOUNT_KEY_FILE")"
key_id="$(jq -r '.id // .key_id // empty' "$YC_SERVICE_ACCOUNT_KEY_FILE")"
test -n "$service_account_id"
test -n "$key_id"

jwt_workdir="$(mktemp -d)"
jwt_private_key="$jwt_workdir/private-key.pem"
jq -r '.private_key // empty' "$YC_SERVICE_ACCOUNT_KEY_FILE" > "$jwt_private_key"
test -s "$jwt_private_key"
chmod 600 "$jwt_private_key"
openssl pkey -in "$jwt_private_key" -noout >/dev/null

jwt_unsigned="$jwt_workdir/unsigned"
jwt_signature="$jwt_workdir/signature.bin"

python3 - "$service_account_id" "$key_id" > "$jwt_unsigned" <<'PY'
import base64
import json
import sys
import time

sa_id, key_id = sys.argv[1:3]

def b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

now = int(time.time())
header = {"typ": "JWT", "alg": "PS256", "kid": key_id}
payload = {
    "iss": sa_id,
    "aud": "https://iam.api.cloud.yandex.net/iam/v1/tokens",
    "iat": now,
    "exp": now + 3600,
}
print(f"{b64url(json.dumps(header, separators=(',', ':')).encode())}.{b64url(json.dumps(payload, separators=(',', ':')).encode())}")
PY

IFS=. read -r jwt_header_part jwt_payload_part < "$jwt_unsigned"
printf '%s.%s' "$jwt_header_part" "$jwt_payload_part" > "$jwt_workdir/signing_input"

openssl dgst -sha256 \
  -sign "$jwt_private_key" \
  -sigopt rsa_padding_mode:pss \
  -sigopt rsa_pss_saltlen:-1 \
  -out "$jwt_signature" "$jwt_workdir/signing_input"

jwt_signature_b64="$(
  python3 - "$jwt_signature" <<'PY'
import base64
import pathlib
import sys
print(base64.urlsafe_b64encode(pathlib.Path(sys.argv[1]).read_bytes()).rstrip(b"=").decode("ascii"))
PY
)"
jwt="$jwt_header_part.$jwt_payload_part.$jwt_signature_b64"

token_response_file="$jwt_workdir/token-response.json"
token_http_code="$(
  curl -sS --connect-timeout 15 --max-time 30 \
    -o "$token_response_file" \
    -w "%{http_code}" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json" \
    -d "$(jq -cn --arg jwt "$jwt" '{jwt: $jwt}')" \
    "https://iam.api.cloud.yandex.net/iam/v1/tokens"
)"
if [[ "$token_http_code" != "200" ]]; then
  echo "IAM JWT exchange failed with HTTP $token_http_code." >&2
  jq -r '.message // .error.message // "IAM JWT exchange failed."' "$token_response_file" >&2 || true
  exit 1
fi

IAM_TOKEN="$(jq -r '.iamToken // .iam_token // empty' "$token_response_file")"
test -n "$IAM_TOKEN"

tmp_policy="$(mktemp)"
cleanup() {
  rm -rf "$jwt_workdir"
  rm -f "$tmp_policy"
}
trap cleanup EXIT

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

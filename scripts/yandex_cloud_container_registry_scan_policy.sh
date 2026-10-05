#!/usr/bin/env bash
set -Eeuo pipefail

: "${YC_REGISTRY_ID:?YC_REGISTRY_ID is required}"
: "${APP_NAME:?APP_NAME is required}"
: "${YC_SERVICE_ACCOUNT_KEY_FILE:?YC_SERVICE_ACCOUNT_KEY_FILE is required}"
test -r "$YC_SERVICE_ACCOUNT_KEY_FILE"

MODE="${1:-ensure}"
case "$MODE" in
  ensure|verify) ;;
  *)
    echo "usage: $0 <ensure|verify>" >&2
    exit 2
    ;;
esac

for command_name in yc jq curl openssl python3; do
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
trap 'rm -rf "$jwt_workdir"' EXIT
jwt_private_key="$jwt_workdir/private-key.pem"
jq -r '.private_key // empty' "$YC_SERVICE_ACCOUNT_KEY_FILE" > "$jwt_private_key"
test -s "$jwt_private_key"
chmod 600 "$jwt_private_key"
openssl pkey -in "$jwt_private_key" -noout >/dev/null

python3 - "$service_account_id" "$key_id" > "$jwt_workdir/unsigned" <<'PY'
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
print(
    f"{b64url(json.dumps(header, separators=(',', ':')).encode())}."
    f"{b64url(json.dumps(payload, separators=(',', ':')).encode())}"
)
PY

IFS=. read -r jwt_header_part jwt_payload_part < "$jwt_workdir/unsigned"
printf '%s.%s' "$jwt_header_part" "$jwt_payload_part" > "$jwt_workdir/signing-input"
openssl dgst -sha256   -sign "$jwt_private_key"   -sigopt rsa_padding_mode:pss   -sigopt rsa_pss_saltlen:-1   -out "$jwt_workdir/signature.bin" "$jwt_workdir/signing-input"

jwt_signature_b64="$(
  python3 - "$jwt_workdir/signature.bin" <<'PY'
import base64
import pathlib
import sys
print(base64.urlsafe_b64encode(pathlib.Path(sys.argv[1]).read_bytes()).rstrip(b"=").decode("ascii"))
PY
)"
jwt="$jwt_header_part.$jwt_payload_part.$jwt_signature_b64"

token_response_file="$jwt_workdir/token-response.json"
token_http_code="$(
  curl -sS --connect-timeout 15 --max-time 30     -o "$token_response_file"     -w "%{http_code}"     -H "Content-Type: application/json"     -H "Accept: application/json"     -d "$(jq -cn --arg jwt "$jwt" '{jwt: $jwt}')"     "https://iam.api.cloud.yandex.net/iam/v1/tokens"
)"
if [[ "$token_http_code" != "200" ]]; then
  echo "IAM JWT exchange failed with HTTP $token_http_code." >&2
  jq -r '.message // .error.message // "IAM JWT exchange failed."' "$token_response_file" >&2 || true
  exit 1
fi

IAM_TOKEN="$(jq -r '.iamToken // .iam_token // empty' "$token_response_file")"
test -n "$IAM_TOKEN"
if [[ -n "${YC_REGISTRY_IAM_TOKEN_FILE:-}" ]]; then
  umask 077
  printf "%s" "$IAM_TOKEN" > "$YC_REGISTRY_IAM_TOKEN_FILE"
fi

policy_name="${APP_NAME}-image-scan"
policy_description="Production vulnerability scanning on push plus daily rescan."

rules_file="$jwt_workdir/scan-policy-rules.json"
cat > "$rules_file" <<'JSON'
{
  "pushRule": {
    "paths": ["*"],
    "disabled": false
  },
  "scheduleRules": [
    {
      "amount": "1",
      "intervalUnit": "DAYS",
      "paths": ["*"],
      "disabled": false
    }
  ]
}
JSON

get_policy() {
  local output_file="$1"
  local rc
  set +e
  yc cloud-registry registry scan-policy get-by-registry "$YC_REGISTRY_ID"     --token "$IAM_TOKEN"     --format=json >"$output_file" 2>&1
  rc=$?
  set -e
  if (( rc == 0 )); then
    echo "200"
    return 0
  fi
  if grep -qiE 'not found|NOT_FOUND|scanPolicyForRegistryNotFoundException' "$output_file"; then
    echo "404"
    return 0
  fi
  echo "$rc"
}

apply_create() {
  yc cloud-registry registry scan-policy create "$policy_name"     --registry-id "$YC_REGISTRY_ID"     --description "$policy_description"     --rules "$rules_file"     --token "$IAM_TOKEN"     --format=json
}

apply_update() {
  local policy_id="$1"
  yc cloud-registry registry scan-policy update "$policy_id"     --new-name "$policy_name"     --new-description "$policy_description"     --new-rules "$rules_file"     --token "$IAM_TOKEN"     --format=json
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
    echo "Container Registry scan policy lookup failed." >&2
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
      (((.rules.pushRule // .rules.push_rule).paths
        // (.rules.push_rule.paths // []))
        | index("*")) != null
    )
    and (((.rules.scheduleRules // .rules.schedule_rules // []) | length) >= 1)
    and ((((.rules.scheduleRules // .rules.schedule_rules // [])[0]).disabled // false) == false)
    and (
      (((.rules.scheduleRules // .rules.schedule_rules // [])[0]).paths
        // ((.rules.schedule_rules // [])[0].paths // []))
        | index("*")) != null
    )
    and (
      (((.rules.scheduleRules // .rules.schedule_rules // [])[0]).amount
        // ((.rules.schedule_rules // [])[0].amount // ""))
      == "1"
    )
    and (
      (((.rules.scheduleRules // .rules.schedule_rules // [])[0]).intervalUnit
        // ((.rules.schedule_rules // [])[0].interval_unit // ""))
      == "DAYS"
    )
  ' --arg registry "$YC_REGISTRY_ID" <<<"$policy_json" >/dev/null
}

if ! policy_matches; then
  [[ "$MODE" == "ensure" ]] || {
    echo "Container Registry scan policy is missing or does not match the production contract." >&2
    exit 1
  }

  if [[ -z "$policy_json" ]]; then
    apply_create >/dev/null
  else
    policy_id="$(jq -r '.id // empty' <<<"$policy_json")"
    test -n "$policy_id"
    apply_update "$policy_id" >/dev/null
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

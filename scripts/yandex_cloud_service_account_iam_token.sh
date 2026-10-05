#!/usr/bin/env bash
set -Eeuo pipefail

: "${YC_SERVICE_ACCOUNT_KEY_FILE:?YC_SERVICE_ACCOUNT_KEY_FILE is required}"
: "${YC_REGISTRY_IAM_TOKEN_FILE:?YC_REGISTRY_IAM_TOKEN_FILE is required}"

for command_name in jq curl openssl python3; do
  command -v "$command_name" >/dev/null 2>&1 || {
    echo "missing required command: $command_name" >&2
    exit 1
  }
done

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT
umask 077

python3 - "$YC_SERVICE_ACCOUNT_KEY_FILE" "$workdir" <<'PY'
import base64
import json
import sys
import time
from pathlib import Path

key_file = Path(sys.argv[1])
workdir = Path(sys.argv[2])
data = json.loads(key_file.read_text(encoding="utf-8"))

key_id = data.get("id")
service_account_id = data.get("service_account_id")
private_key = data.get("private_key")
if not key_id or not service_account_id or not private_key:
    raise SystemExit("Yandex service-account key is missing id, service_account_id or private_key")

if private_key.startswith("PLEASE DO NOT REMOVE THIS LINE!"):
    _, private_key = private_key.split("\n", 1)

(workdir / "private.pem").write_text(private_key, encoding="utf-8")

now = int(time.time())
header = {
    "typ": "JWT",
    "alg": "PS256",
    "kid": key_id,
}
payload = {
    "iss": service_account_id,
    "aud": "https://iam.api.cloud.yandex.net/iam/v1/tokens",
    "iat": now,
    "exp": now + 3600,
}

def b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

signing_input = ".".join(
    (
        b64url(json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode("utf-8")),
        b64url(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")),
    )
)
(workdir / "signing_input.txt").write_text(signing_input, encoding="ascii")
PY

openssl dgst -sha256   -sign "$workdir/private.pem"   -sigopt rsa_padding_mode:pss   -sigopt rsa_pss_saltlen:-1   -out "$workdir/signature.bin"   "$workdir/signing_input.txt"

signature="$(
  python3 - "$workdir/signature.bin" <<'PY'
import base64
import sys
from pathlib import Path

raw = Path(sys.argv[1]).read_bytes()
print(base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii"))
PY
)"

jwt="$(cat "$workdir/signing_input.txt").$signature"
jq -n --arg jwt "$jwt" '{jwt: $jwt}' > "$workdir/request.json"

http_code="$(
  curl -sS     --connect-timeout 10     --max-time 30     -o "$workdir/response.json"     -w "%{http_code}"     -H "Content-Type: application/json"     --data-binary @"$workdir/request.json"     "https://iam.api.cloud.yandex.net/iam/v1/tokens"
)"

if [[ "$http_code" != "200" ]]; then
  echo "Yandex IAM JWT exchange failed with HTTP $http_code." >&2
  jq -r '.message // .error.message // "IAM token exchange failed."' "$workdir/response.json" >&2 || true
  exit 1
fi

iam_token="$(jq -r '.iamToken // empty' "$workdir/response.json")"
test -n "$iam_token"

umask 077
printf "%s" "$iam_token" > "$YC_REGISTRY_IAM_TOKEN_FILE"
chmod 600 "$YC_REGISTRY_IAM_TOKEN_FILE"
echo "IAM_TOKEN_SOURCE=service_account_jwt"

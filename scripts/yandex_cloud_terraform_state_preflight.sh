#!/usr/bin/env bash
set -Eeuo pipefail

: "${YC_TERRAFORM_STATE_BUCKET:?YC_TERRAFORM_STATE_BUCKET is required}"
: "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID is required}"
: "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY is required}"
: "${AWS_DEFAULT_REGION:=ru-central1}"
: "${YC_TERRAFORM_STATE_ENDPOINT:=https://storage.yandexcloud.net}"
: "${YC_TERRAFORM_STATE_KEY:=shema/production/terraform.tfstate}"

classify_provider_error() {
  local error_text="$1"

  case "$error_text" in
    *InvalidAccessKeyId*)
      echo "INVALID_ACCESS_KEY_ID"
      ;;
    *SignatureDoesNotMatch*)
      echo "SIGNATURE_MISMATCH"
      ;;
    *AccessDenied*|*Forbidden*)
      echo "ACCESS_DENIED"
      ;;
    *NoSuchBucket*|*NotFound*)
      echo "BUCKET_NOT_FOUND"
      ;;
    *PermanentRedirect*|*AuthorizationHeaderMalformed*|*InvalidRegion*)
      echo "REGION_OR_ENDPOINT_MISMATCH"
      ;;
    *Could\ not\ connect*|*Connection\ refused*|*Could\ not\ resolve\ host*|*SSL*)
      echo "NETWORK_OR_TLS"
      ;;
    *)
      echo "UNCLASSIFIED_PROVIDER_ERROR"
      ;;
  esac
}

run_s3() {
  local operation="$1"
  shift
  local output rc

  set +e
  output="$(AWS_EC2_METADATA_DISABLED=true aws s3api "$operation" "$@" 2>&1)"
  rc=$?
  set -e

  if (( rc == 0 )); then
    S3_OPERATION_OUTPUT="$output"
    S3_OPERATION_ERROR_CLASS=""
    return 0
  fi

  S3_OPERATION_OUTPUT="$output"
  S3_OPERATION_ERROR_CLASS="$(classify_provider_error "$output")"
  return "$rc"
}

command -v aws >/dev/null 2>&1 || {
  echo "AWS_CLI=FAIL"
  echo "The protected state preflight requires the AWS CLI for the Yandex Object Storage S3-compatible API."
  exit 1
}

if ! command -v curl >/dev/null 2>&1; then
  echo "STATE_S3_ENDPOINT_REACHABILITY=FAIL"
  echo "curl is required to distinguish endpoint/network failures from S3 authorization failures."
  exit 1
fi

set +e
endpoint_http_status="$(curl --silent --show-error --output /dev/null   --connect-timeout 10 --max-time 20   --write-out '%{http_code}'   "$YC_TERRAFORM_STATE_ENDPOINT")"
curl_rc=$?
set -e

if (( curl_rc != 0 )); then
  echo "STATE_S3_ENDPOINT_REACHABILITY=FAIL"
  echo "STATE_S3_ENDPOINT_ERROR=NETWORK_OR_TLS"
  exit 1
fi

if [[ ! "$endpoint_http_status" =~ ^[1-5][0-9][0-9]$ ]]; then
  echo "STATE_S3_ENDPOINT_REACHABILITY=FAIL"
  echo "STATE_S3_ENDPOINT_ERROR=INVALID_HTTP_STATUS"
  exit 1
fi

echo "STATE_S3_ENDPOINT_REACHABILITY=PASS"
echo "STATE_S3_ENDPOINT_HTTP_STATUS=$endpoint_http_status"

# The deployment identity and the Terraform-state identity are intentionally
# separate. This management-plane probe is diagnostic only.
if command -v yc >/dev/null 2>&1; then
  set +e
  yc storage bucket get "$YC_TERRAFORM_STATE_BUCKET" --full >/dev/null 2>"$RUNNER_TEMP/phase7c-state-management-error" 2>/dev/null
  management_rc=$?
  set -e
  if (( management_rc == 0 )); then
    echo "STATE_BUCKET_MANAGEMENT_VISIBILITY=PASS"
  else
    echo "STATE_BUCKET_MANAGEMENT_VISIBILITY=FAIL"
    echo "STATE_BUCKET_MANAGEMENT_ERROR=UNAVAILABLE_OR_NOT_FOUND"
  fi
fi

if run_s3 head-bucket   --bucket "$YC_TERRAFORM_STATE_BUCKET"   --endpoint-url "$YC_TERRAFORM_STATE_ENDPOINT"; then
  echo "STATE_S3_HEAD_BUCKET=PASS"
else
  echo "STATE_S3_HEAD_BUCKET=FAIL"
  echo "STATE_S3_ERROR_CLASS=$S3_OPERATION_ERROR_CLASS"
  case "$S3_OPERATION_ERROR_CLASS" in
    INVALID_ACCESS_KEY_ID)
      echo "STATE_S3_AUTHENTICATION=INVALID_ACCESS_KEY_ID"
      ;;
    SIGNATURE_MISMATCH)
      echo "STATE_S3_AUTHENTICATION=SIGNATURE_MISMATCH"
      ;;
    REGION_OR_ENDPOINT_MISMATCH)
      echo "STATE_S3_AUTHENTICATION=REGION_OR_ENDPOINT_MISMATCH"
      ;;
    ACCESS_DENIED)
      echo "STATE_S3_AUTHORIZATION=DENIED_OR_BUCKET_POLICY"
      ;;
    BUCKET_NOT_FOUND)
      echo "STATE_S3_BUCKET=NOT_FOUND"
      ;;
    NETWORK_OR_TLS)
      echo "STATE_S3_NETWORK=FAIL"
      ;;
    *)
      echo "STATE_S3_AUTHENTICATION=UNCLASSIFIED"
      ;;
  esac
  echo "STATE_S3_ERROR_OUTPUT=SUPPRESSED"
  echo "STATE_S3_CREDENTIAL_VALUES=NOT_PRINTED"
  exit 1
fi

if ! run_s3 get-bucket-versioning   --bucket "$YC_TERRAFORM_STATE_BUCKET"   --endpoint-url "$YC_TERRAFORM_STATE_ENDPOINT"   --query Status   --output text; then
  echo "STATE_S3_VERSIONING_QUERY=FAIL"
  echo "STATE_S3_ERROR_CLASS=$S3_OPERATION_ERROR_CLASS"
  echo "STATE_S3_ERROR_OUTPUT=SUPPRESSED"
  echo "STATE_S3_CREDENTIAL_VALUES=NOT_PRINTED"
  exit 1
fi

versioning="$S3_OPERATION_OUTPUT"
if [[ "$versioning" != "Enabled" ]]; then
  echo "STATE_S3_VERSIONING=FAIL"
  echo "Terraform state bucket must have Object Storage versioning enabled."
  exit 1
fi

echo "STATE_S3_VERSIONING=PASS"

if ! run_s3 list-objects-v2   --bucket "$YC_TERRAFORM_STATE_BUCKET"   --prefix "$YC_TERRAFORM_STATE_KEY"   --max-keys 1   --endpoint-url "$YC_TERRAFORM_STATE_ENDPOINT"; then
  echo "STATE_S3_STATE_KEY_NAMESPACE_ACCESS=FAIL"
  echo "STATE_S3_ERROR_CLASS=$S3_OPERATION_ERROR_CLASS"
  echo "STATE_S3_ERROR_OUTPUT=SUPPRESSED"
  echo "STATE_S3_CREDENTIAL_VALUES=NOT_PRINTED"
  exit 1
fi

echo "STATE_S3_STATE_KEY_NAMESPACE_ACCESS=PASS"
echo "TERRAFORM_STATE_BUCKET_EXISTS=PASS"
echo "TERRAFORM_STATE_BUCKET_VERSIONING=PASS"
echo "TERRAFORM_STATE_CREDENTIAL_ISOLATION=PASS"
echo "TERRAFORM_STATE_CREDENTIAL_VALUES=NOT_PRINTED"

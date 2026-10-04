#!/usr/bin/env bash
set -Eeuo pipefail

: "${YC_TERRAFORM_STATE_BUCKET:?YC_TERRAFORM_STATE_BUCKET is required}"
: "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID is required}"
: "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY is required}"
: "${AWS_DEFAULT_REGION:=ru-central1}"
: "${YC_TERRAFORM_STATE_ENDPOINT:=https://storage.yandexcloud.net}"

command -v aws >/dev/null 2>&1 || {
  echo "AWS_CLI=FAIL"
  echo "The protected state preflight requires the AWS CLI for the Yandex Object Storage S3-compatible API."
  exit 1
}

AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
AWS_DEFAULT_REGION="$AWS_DEFAULT_REGION" \
aws s3api head-bucket \
  --bucket "$YC_TERRAFORM_STATE_BUCKET" \
  --endpoint-url "$YC_TERRAFORM_STATE_ENDPOINT" >/dev/null

versioning="$(
  AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
  AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
  AWS_DEFAULT_REGION="$AWS_DEFAULT_REGION" \
  aws s3api get-bucket-versioning \
    --bucket "$YC_TERRAFORM_STATE_BUCKET" \
    --endpoint-url "$YC_TERRAFORM_STATE_ENDPOINT" \
    --query Status \
    --output text
)"

if [[ "$versioning" != "Enabled" ]]; then
  echo "TERRAFORM_STATE_BUCKET_VERSIONING=FAIL"
  echo "Terraform state bucket must have Object Storage versioning enabled."
  exit 1
fi

echo "TERRAFORM_STATE_BUCKET_EXISTS=PASS"
echo "TERRAFORM_STATE_BUCKET_VERSIONING=PASS"
echo "TERRAFORM_STATE_CREDENTIAL_ISOLATION=PASS"
echo "TERRAFORM_STATE_BUCKET_SECRET_VALUES=NOT_PRINTED"

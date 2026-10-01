#!/usr/bin/env bash
set -Eeuo pipefail

: "${YC_TERRAFORM_STATE_BUCKET:?YC_TERRAFORM_STATE_BUCKET is required}"

bucket_json="$(yc storage bucket get "$YC_TERRAFORM_STATE_BUCKET" --format=json)"
versioning="$(jq -r '.versioning // empty' <<<"$bucket_json")"

if [[ "$versioning" != "VERSIONING_ENABLED" ]]; then
  echo "TERRAFORM_STATE_BUCKET_VERSIONING=FAIL"
  echo "Terraform state bucket must have Object Storage versioning enabled."
  exit 1
fi

echo "TERRAFORM_STATE_BUCKET_EXISTS=PASS"
echo "TERRAFORM_STATE_BUCKET_VERSIONING=PASS"
echo "TERRAFORM_STATE_BUCKET_SECRET_VALUES=NOT_PRINTED"

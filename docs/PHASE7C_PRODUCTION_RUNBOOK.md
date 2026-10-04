# Phase 7C — Production Execution Runbook

## Purpose

This runbook is the operational handoff for the final Phase 7C live-evidence boundary. It does not change domain semantics and must be executed only through the protected `production-yandex` GitHub environment.

## Required protected GitHub environment inputs

The `production-yandex` environment must contain the already-defined Phase 7C inputs plus the persistent Terraform state credentials:

- `YC_SERVICE_ACCOUNT_KEY_JSON`
- `PHASE7C_TFVARS_JSON` (contains operator-supplied OIDC values and the write-only PostgreSQL credential input; image URL/digest are filled by the protected bootstrap)
- `PHASE7C_CLOUD_ID`
- `PHASE7C_FOLDER_ID`
- `PHASE7C_CONTAINER_NAME`
- `PHASE7C_MIGRATION_RUNNER_NAME`
- `PHASE7C_CLUSTER_NAME`
- `PHASE7C_BUCKET_NAME`
- `PHASE7C_BUDGET_ID`
- `PHASE7C_TERRAFORM_STATE_BUCKET`
- `PHASE7C_TERRAFORM_STATE_ACCESS_KEY_ID`
- `PHASE7C_TERRAFORM_STATE_SECRET_KEY`

No secret value belongs in the repository, workflow YAML, plan output, logs, or evidence files.

The protected workflow derives the PostgreSQL connection DSN from the private cluster primary FQDN after cluster creation and stores it in Lockbox. `database_url` is therefore not an operator input and must not be added as a GitHub secret.

## Terraform state bootstrap

Use a dedicated Yandex Object Storage bucket for Terraform state. It must be separate from the application's bounded object bucket.

The state bucket must:

1. exist before the Phase 7C workflow runs;
2. have Object Storage versioning enabled;
3. remain non-public;
4. be reachable by the dedicated state service account;
5. use a dedicated static Access Key ID + Secret Access Key;
6. remain outside the application Terraform state to avoid a bootstrap cycle.

The state preflight uses the dedicated S3 credentials directly. `YC_SERVICE_ACCOUNT_KEY_JSON` is not a substitute and must not be granted state-bucket access merely to make preflight pass.

The state backend is fixed to:

`shema/production/terraform.tfstate`

and uses the Yandex Object Storage S3 endpoint with Terraform S3 lockfile configuration.

For the dedicated state service account, `storage.editor` is sufficient for object read/write/delete operations; bucket access should be scoped as narrowly as the operating environment permits.

## Mature Yandex Cloud production baseline

For this product shape the production baseline is:

- Serverless Containers remain the runtime authority; Kubernetes is not introduced without a measured scaling or operational requirement.
- Managed PostgreSQL remains the single transactional authority; the current two-host, two-AZ HA baseline is retained.
- API Gateway is the public edge; application containers remain private and IAM-invoked.
- Lockbox is the runtime secret authority; production credentials are externalized.
- Container images are immutable digest-pinned artifacts.
- Terraform uses remote Object Storage state, dedicated state credentials, bucket versioning and S3 lockfile semantics.
- Runtime and task logs use dedicated Cloud Logging groups with bounded retention.
- Audit Trails collects management and relevant Object Storage data events into the dedicated audit log group.
- Container Registry vulnerability scanning is enabled on push and on a scheduled rescan.
- Custom-domain support is conditional and requires a Certificate Manager certificate ID.
- Budget configuration remains a protected external input; live evidence verifies an active budget and at least one threshold.

The deployment identity and Terraform-state identity are intentionally separate as a least-privilege boundary.

### Deployment identity minimum for the registry bootstrap

The service account behind `YC_SERVICE_ACCOUNT_KEY_JSON` must have `container-registry.editor` on the target folder. The protected workflow creates the production Container Registry when it is absent and manages its scan policy and image lifecycle. A pull-only registry role is insufficient for this deployment identity.

The runtime and migration identities remain separately scoped to image pulling; they must not inherit the deployment bootstrap role merely for runtime operation.

## First-run bootstrap boundary

The first protected run has one deliberate bootstrap side effect before the reviewed production plan: it creates the expected `shema-images` Container Registry when absent, imports that registry into the production Terraform state, and builds/pushes the current Git commit as an immutable digest-pinned image. The workflow never deploys a mutable tag as the runtime authority. With `apply=false`, no production runtime resources are applied; registry/image bootstrap is the only intentional preparation side effect.

The initial installation has no previous serverless-container revision, so `rollback_drill` must remain `false` on the first successful production apply. Subsequent runs may enable it.

## Execution sequence

Run the workflow manually with:

- `apply=false` for plan/evidence preparation and manual review;
- after review, `apply=true`;
- `rollback_drill=true` for the protected immutable-revision rollback proof;
- `pitr_drill=true` with a valid RFC3339 UTC recovery target once an eligible automated backup exists.

The workflow is deliberately fail-closed:

- remote state preflight must pass;
- Terraform plan is generated and fingerprinted;
- the apply job recomputes the plan and refuses execution if the fingerprint changed;
- the apply uses the verified plan file rather than generating an unrelated second apply plan.

## 8A. Observability platform lifecycle

Yandex currently documents Cloud Logging as a transition path and recommends migration to the Monium Observability Platform before the Cloud Logging retirement window. The current Terraform provider surface used by this repository does not expose a first-class Monium resource model.

Accordingly, the deployed 7C Terraform baseline uses explicit Cloud Logging groups as the currently supported IaC path, with the migration target recorded as Monium. No unsupported provider resource or undocumented API call is introduced. Any Monium migration must update Terraform/ops configuration, live-evidence checks and this runbook as one controlled change and must pass the same complete release gate and live observability evidence before closure.

## Closure evidence

Phase 7C can move to CLOSED / VERIFIED only after live evidence proves:

- infrastructure provisioning;
- persistent Terraform state;
- database connectivity and migrations from the same VPC;
- Lockbox delivery;
- API Gateway edge readiness and production smoke;
- immutable image digest integrity;
- logging/observability and budget thresholds;
- dedicated runtime and audit log groups;
- active Audit Trail;
- active Container Registry vulnerability-scan policy with push and scheduled rules;
- backup retention;
- PITR recovery and cleanup;
- immutable rollback and restoration;
- final global adversarial review;
- final current-head seven-job gate.

The repository-side implementation gate is already green; these remaining items are production evidence, not placeholders.

## Recovery safety

PITR must restore into a separate PRESTABLE cluster with no public database IP. Recovery verification uses the same immutable application image digest and a private task-mode runner. The production database must not be mutated by the drill. Temporary recovery resources must be cleaned up on success, failure, and cancellation.

## Credential rotation

Rotate the dedicated Object Storage state access key and all production service credentials according to the operational security policy. Never paste secret values into issues, PR comments, chat messages, commits or logs.

## License

The repository is licensed under Apache-2.0. Third-party dependencies remain under their respective licenses.

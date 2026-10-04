# Yandex Cloud Mature Production Baseline — Phase 7C

**Research date:** 2026-10-04  
**Repository:** `LIK-HO/shema-business-platform`  
**Boundary:** Phase 7C — Cloud resource provisioning + live evidence

## Executive decision

The current product shape does not require Managed Kubernetes. Yandex Serverless Containers + API Gateway + Managed PostgreSQL + Lockbox + Container Registry + Cloud Logging/Audit Trails + Object Storage/Terraform state is a mature and operationally appropriate baseline.

The baseline is designed around a small canonical system, low operational overhead, explicit IAM boundaries, immutable releases, private transactional infrastructure and independently verifiable recovery.

## 1. Mature deployment lifecycle

The mature lifecycle is:

1. Build and test the exact source revision.
2. Produce an immutable container artifact.
3. Scan the artifact for vulnerabilities.
4. Store infrastructure state remotely with locking and versioning.
5. Generate a reviewed Terraform plan.
6. Bind apply to the exact source revision and reviewed plan fingerprint.
7. Provision private network, identities, runtime, database, secrets and edge.
8. Run migrations through a private same-VPC task, not through a public debug endpoint.
9. Verify health, authentication failure paths, edge readiness and immutable revision identity.
10. Verify observability, audit trail, budget threshold and security controls.
11. Prove rollback to the previous immutable revision.
12. Prove PITR into a separate private recovery cluster.
13. Run global adversarial and regression review on the exact current HEAD.
14. Only then close the production boundary.

## 2. Identity and least privilege

Deployment/resource API identity and Terraform-state identity are separate.

- Deployment identity: `YC_SERVICE_ACCOUNT_KEY_JSON`.
- Terraform state identity: dedicated Object Storage static Access Key ID + Secret Access Key.
- Runtime identity: dedicated Serverless Container service account.
- Gateway invoker: separate least-privilege service account.
- Migration/evidence runner: separate private task identity.
- Audit Trail identity: separate identity with only the roles needed for audit collection.

The state bucket is not accessed by the deployment identity.

## 3. Runtime architecture

The production edge is API Gateway. The application container is private and invoked by an IAM-bound gateway identity.

Serverless Containers are the canonical runtime because they provide immutable revisions, Container Registry image integration, private network connectivity and autoscaling without the operational surface of a Kubernetes control plane.

Kubernetes is deliberately conditional: it becomes justified only when measurable requirements exceed the Serverless Containers operating model.

## 4. Network and database

The approved network uses all required `ru-central1` availability zones and keeps PostgreSQL private.

Production PostgreSQL uses:

- Managed PostgreSQL;
- two hosts in different availability zones as the current HA baseline;
- no public database IP;
- private security-group ingress;
- port 6432;
- TLS `verify-full`;
- current-master writable endpoint;
- automated backups with 14-day retention;
- separate-cluster PITR validation.

A third PostgreSQL host is not added merely for appearance of maturity. It becomes justified when measurable availability, read-scaling or maintenance requirements require it.

## 5. Secrets

Lockbox is the runtime secret authority.

The application receives OIDC and database credentials from Lockbox. PostgreSQL credentials use write-only input and an explicit version number so rotation is observable and controlled.

Secrets are never required in repository source, workflow YAML, artifacts, evidence or logs.

## 6. Artifacts and supply chain

Container Registry is the artifact authority.

Runtime deployment is digest-pinned rather than tag-authoritative. The current baseline enables:

- scan on push;
- scheduled rescan;
- language-package vulnerability scanning;
- immutable digest verification before deployment.

The evidence gate verifies that the active runtime revision uses the digest produced by the protected bootstrap.

## 7. Terraform state

The Terraform state is remote in Yandex Object Storage.

Required controls:

- dedicated state bucket;
- versioning enabled;
- non-public bucket;
- dedicated state credentials;
- S3-compatible backend;
- lockfile enabled;
- fixed state key `shema/production/terraform.tfstate`;
- reviewed-plan fingerprint bound to apply.

A preflight failure is a hard stop. It must not be bypassed by granting the deployment service account broader state access.

## 8. Observability and audit

Runtime and task logs use dedicated Cloud Logging groups with explicit retention.

Audit Trails is enabled for management activity and relevant Object Storage data events and writes to the dedicated audit log group.

Live evidence therefore distinguishes:

- application/task log ingestion;
- audit log retention;
- audit trail activity;
- billing budget controls.

## 9. Budget and cost controls

A mature deployment does not assume that a budget threshold stops resource consumption. Budget thresholds are an alerting/control-plane boundary.

The project keeps the budget ID externalized as a protected input and requires live evidence of an active budget with at least one threshold.

Terraform does not invent a budget resource where the current provider surface does not expose one; operational billing configuration remains an explicit external dependency.

## 10. Custom domain

Custom domains are optional, not required for the baseline.

When enabled:

- the API Gateway hostname is explicitly configured;
- a valid Certificate Manager certificate ID is mandatory;
- configuration fails closed when the certificate is missing.

No domain certificate is required while the product is still using the generated API Gateway hostname.

## 11. Recovery

Rollback and recovery are separate proofs.

Rollback:
- capture previous active revision;
- deploy new immutable revision;
- smoke;
- rollback to previous immutable revision;
- verify;
- restore the new immutable revision;
- verify again.

PITR:
- choose an eligible automated backup;
- restore a new PRESTABLE PostgreSQL cluster;
- keep it private and in the production VPC;
- use the same immutable application image;
- verify connection and migration state;
- delete all temporary recovery resources;
- never mutate the production cluster.

## 12. What was changed in Phase 7C

The mature-baseline branch implements:

- dedicated Terraform-state S3 preflight credentials;
- credential-isolation contract and regression tests;
- custom runtime and audit Cloud Logging groups;
- Audit Trail;
- Container Registry scan policy;
- non-deprecated Object Storage bucket-grant configuration;
- optional Certificate Manager custom-domain binding;
- live evidence for runtime/audit/scan controls;
- runbook updates describing the production identity boundaries.

## 13. Conditional items deliberately not added

These are not maturity requirements for this product at its current measured scale:

- Managed Kubernetes;
- third PostgreSQL host;
- service mesh;
- separate message broker;
- second transactional database;
- bespoke internal secrets service;
- mandatory custom domain;
- complex multi-region active-active deployment.

Adding them without a measured operational need would increase failure surface and undermine the project's bounded-complexity rule.

## 14. Closure standard

The architecture is not called production-ready from repository code alone.

Phase 7C remains open until real Yandex Cloud evidence proves:

- state backend access and locking;
- successful Terraform apply;
- private network and runtime;
- database connectivity and migrations;
- Lockbox delivery;
- API Gateway smoke;
- immutable digest;
- runtime/audit logging;
- Audit Trail;
- vulnerability scan policy;
- budget thresholds;
- backup retention;
- PITR and cleanup;
- rollback and restoration;
- current-head global adversarial review;
- final current-head seven-job release gate.

## Primary official references

- Yandex Serverless Containers logging: https://yandex.cloud/en/docs/serverless-containers/operations/logs-write
- Yandex Container Registry vulnerability scanner: https://yandex.cloud/en/docs/container-registry/concepts/vulnerability-scanner
- Yandex Container Registry scan policy CLI: https://yandex.cloud/en/docs/cloud-registry/cli-ref/v0/registry/scan-policy/
- Yandex Audit Trails management: https://yandex.cloud/en/docs/audit-trails/operations/manage-trail
- Yandex Terraform state locking: https://yandex.cloud/en/docs/terraform/tutorials/terraform-state-lock

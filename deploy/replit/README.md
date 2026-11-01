# Replit deployment module

**Status:** configuration and fail-closed deployment controls are implemented; the platform is **not yet eligible for production publication**.

This module adds a bounded Replit Reserved VM deployment target without moving source control, release evidence or business truth away from their existing authorities.

## 1. Architecture decision

- **GitHub remains canonical:** repository, code review, protected release history and the complete seven-job CI gate.
- **Replit Reserved VM is the target runtime:** one persistent HTTP API process. Static hosting is unsuitable for FastAPI; Autoscale is not selected for the first deployment because the service needs a predictable always-on API process.
- **PostgreSQL remains the only transactional authority.** A dedicated production database must be configured for the published app. The development database is not a production database.
- **No business data is stored on the Replit deployment filesystem.** It is an immutable application/runtime layer, not persistent storage.
- **No automatic migrations run at process startup.** Migrations are a separately approved, one-off operation.
- **No kernel, domain or database semantics are changed by this deployment module.**

## 2. Important production data-location blocker

The Replit publishing geography currently documented by Replit does not include the Russian Federation. The region is selected during the first publication and is not freely changeable afterwards. Replit also places deployment compute and its managed database in the selected region.

The platform may process Russian individual contact details, names, telephone numbers and other personal data. Article 18(5) of Federal Law 152-FZ restricts collection and the related recording, systematization, accumulation, storage, updating and extraction of personal data of Russian citizens in databases outside the Russian Federation, subject to specific statutory exceptions. The Ministry of Digital Development's 12 May 2025 explanatory letter also discusses subsequent updates, copies and separate cross-border transfer requirements.

Therefore, the current module **only permits synthetic data** through REPLIT_DATA_MODE=synthetic_only. It does not authorize importing, copying, submitting or processing real Russian personal data in Replit. This is an engineering safety gate, not a legal opinion. A qualified legal review must determine the operator's role, data categories, collection context, statutory basis, localization and any lawful cross-border transfer before this restriction can be changed.

Do not choose a Replit region or create a production database until the data-location decision is documented. Selecting a region for a first publish may be irreversible.

## 3. Replit deployment configuration

The root .replit file contains the deployment build and run commands and exactly one externally exposed HTTP port.

In the Replit Publish flow, select:

1. **Reserved VM** deployment.
2. A machine tier based on measured CPU and memory demand, not an arbitrary maximum.
3. A region only after data-protection review. An EU region is not a substitute for Russian data localization.
4. A dedicated **production PostgreSQL database** for the published application.
5. Do not copy the Replit development database into production.
6. Review production secrets and usage/billing controls before publishing.

The VM is expected to serve HTTP on 0.0.0.0 and the internal PORT value (default 8080). Replit maps one internal application port to external HTTPS port 80. TLS termination and the public HTTPS endpoint are provided by Replit. Do not expose PostgreSQL or worker/admin ports to the public internet.

## 4. Required Replit production secrets

Add secrets in the published deployment's production configuration. Do not commit values to Git, put them in .replit, log them or expose them to browser code.

| Secret | Requirement |
|---|---|
| DATABASE_URL | Dedicated production PostgreSQL connection string |
| OIDC_ISSUER | HTTPS issuer URL |
| OIDC_AUDIENCE | Exact API audience |
| OIDC_JWKS_URL | HTTPS JWKS URL on the same host as the issuer |
| REPLIT_DATA_MODE | Must be exactly synthetic_only under the current approval boundary |
| REPLIT_MIGRATION_APPROVED | Set to YES only for a separately reviewed migration invocation |
| REPLIT_BACKUP_REFERENCE | Required for adoption of an existing schema; identifies a verified backup outside the deployment filesystem |

APP_ENV=production is set by the run script. PORT is supplied by the deployment environment.

Other provider credentials are intentionally not enumerated here. Add only providers whose readiness, legal basis, activation evidence and application composition have independently passed their existing contracts. Do not activate AI, data or communication providers as a side effect of deployment.

## 5. Startup and runtime safety

deploy/replit/run.sh:

1. sets APP_ENV=production;
2. executes the preflight;
3. starts Uvicorn only if every gate passes.

The preflight checks:
- production mode and synthetic-only data mode;
- a non-local PostgreSQL DATABASE_URL;
- HTTPS OIDC issuer/JWKS and audience;
- valid listen port;
- a real production APIApplication, authenticator, resource-read authorizer and telemetry composition;
- PostgreSQL connectivity;
- the complete migration ledger, including contiguous versions and exact SQL checksums.

Errors are emitted as stable reason codes. Database exceptions and connection strings are never printed.

The current src/shema_platform/experience/production.py entrypoint constructs the HTTP edge without an APIApplication or resource-read authorizer. The preflight therefore correctly blocks startup with production_application_not_composed and production_resource_read_authorizer_not_composed. Do not remove these checks to make the deployment appear healthy.

The existing /health/ready endpoint is a provider-readiness endpoint. It is not, by itself, proof of database health, runtime composition, worker availability or full product readiness. The preflight and the later production acceptance suite must validate those concerns independently.

## 6. Database migrations

Use the guarded migration tool from a Replit shell or a controlled operator environment with the exact approved GitHub commit checked out.

Plan only:

    python deploy/replit/migrate.py

Apply a fresh schema after review:

    APP_ENV=production REPLIT_DATA_MODE=synthetic_only \
    REPLIT_MIGRATION_APPROVED=YES \
    python deploy/replit/migrate.py --apply

Adopt an existing v1.4 schema only after confirming its structure and completing a verified backup:

    APP_ENV=production REPLIT_DATA_MODE=synthetic_only \
    REPLIT_MIGRATION_APPROVED=YES \
    REPLIT_BACKUP_REFERENCE='<verified-backup-reference>' \
    python deploy/replit/migrate.py --apply --adopt-existing-schema

The migration runner uses the repository's existing advisory lock, migration ledger and SQL checksums. The process does not delete data, rewrite previous migration checksums or run automatically on every web process restart. The first-time schema creation and legacy-schema adoption are different paths; do not use adoption for an empty database or apply the full initial DDL over an existing schema.

A successful migration command is not a backup. Verify a backup and restore path separately before using real data.

## 7. Release and rollback procedure

1. Create a scoped branch from the live main HEAD.
2. Implement one bounded change and open a pull request.
3. Run the complete seven-job GitHub CI and review all changed files and contracts.
4. Merge only after all required reviews and checks pass.
5. In Replit, pull/import the exact approved main commit. Confirm its SHA matches the merged GitHub commit.
6. Review production secrets, data mode, region, production database, VM tier and cost controls.
7. Back up the database; apply reviewed migrations as a one-off operation.
8. Publish the Reserved VM build and run the complete production acceptance suite.
9. Record the deployment ID, public URL, release commit, migration version, health results and rollback reference.

Rollback means republishing the last known-good immutable application commit and, only where necessary, performing a separately rehearsed database recovery. Reverting application code does not automatically reverse schema changes. Never attempt a destructive schema rollback without a tested recovery plan.

## 8. Cost and capacity controls

Reserved VM compute is billed according to the selected machine tier and runtime; it is not costed solely by request volume. Database compute/storage and outbound transfer may add separate usage. Review the current account's actual plan, machine tier, usage and billing page before publication. Set an explicit budget/usage limit and alerting appropriate to the account. No fixed monthly price is embedded here because the exact current entitlement and machine selection are account-specific.

Start with the smallest tier that passes measured load and memory tests. Increase it only when production measurements justify the change. Do not run the API, a duplicate API, and a job worker inside an unbounded shell supervisor.

## 9. Current production blockers

The module is intentionally not a production approval. The following work remains:

1. Build and test the complete production application composition in production.py; current startup fails closed.
2. Compose and operate the durable job/worker and outbox execution plane as a separately bounded service. A web process alone does not execute all durable background work.
3. Complete the 152-FZ localization and cross-border data review for the actual data inventory and deployment geography.
4. Prove Replit production PostgreSQL backup, independent export, restore and recovery time against the platform's existing recovery objectives.
5. Confirm the account plan, eligible region, Reserved VM tier, production database location and cost limit.
6. Run integration, authenticated E2E, negative, failure, restart, migration, backup/restore and rollback drills against the actual Replit deployment.

Until all applicable blockers are closed with evidence, the deployment remains **BLOCKED — SYNTHETIC/CONTROLLED VALIDATION ONLY; NOT PRODUCTION-READY**.

# Replit deployment contract

**Status: FOUNDATION ONLY — NOT RELEASE-AUTHORIZED**

This contract defines a reproducible Replit staging path for the existing provider-neutral
Python/FastAPI application. It does not assert that the business runtime is fully composed,
that PostgreSQL is provisioned, or that any external provider is active.

## Scope and source of truth

- Canonical source: this Git repository and its reviewed branch/commit.
- Replit is a runtime target, not a second source of business truth.
- PostgreSQL remains the transactional source of truth.
- Do not change the frozen kernel or introduce provider-specific deployment assumptions.
- The public website and protected operator console must use the same canonical API and
  authorization model. Browser storage must not become a business database.
- The B2B public website/intake and operator lead-development experience are product scope;
  this deployment foundation alone does not implement those features.

## Build and run contract

- Python: supported project range `>=3.12`; CI validates 3.12 and 3.13.
- Install: `python -m pip install --upgrade pip && python -m pip install .`
- Run: `uvicorn shema_platform.experience.production:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers`
- Replit must provide the runtime `PORT`. Bind to `0.0.0.0`; never hardcode localhost.
- Do not run database schema migrations implicitly during web-process startup.
- A deployment is not ready merely because the process starts or a port is open.

## Required environment and secret policy

Configure secrets in Replit Secrets / deployment secrets, never in Git, source code,
`.replit`, logs, client-side assets, or screenshots.

Potentially required after the corresponding runtime is composed:
- `DATABASE_URL`: PostgreSQL connection URI from the intended environment.
- OIDC issuer, audience and JWKS configuration required by the server-side authenticator.
- Explicit allowlisted public origins and server-side bot-challenge verification for public intake.
- Provider credentials only when that provider is approved for activation.

Never copy production credentials or production data into development/staging. Use least-privilege
database roles and separate databases for development, staging and production. Fail closed when
required security configuration is missing. Do not activate AI, registry lookups, or outbound
communications by merely adding secrets.

## Release gates

A Replit staging deployment may be considered for acceptance only after evidence exists for all
applicable items:

1. The exact GitHub commit and dependency set are identified and reproducible.
2. Static checks, unit tests, integration tests against PostgreSQL, supply-chain audit,
   backup/recovery drill and release-contract validation pass on that commit.
3. The Replit build and process start successfully from the checked-in configuration.
4. Liveness and readiness semantics are distinct and verified; readiness must not return success
   while required dependencies or runtime capabilities are absent.
5. Apply all database migrations to a clean staging database and test the supported upgrade path.
6. Verify public landing page/intake, origin allowlist, rate limiting, bot challenge, idempotency,
   and data minimization.
7. Verify operator authentication, authorization boundaries, session handling and denial paths.
8. Verify lead search, evidence/identity handling, persistence, audit lineage and operator workflow
   end-to-end once those capabilities are composed.
9. Verify PostgreSQL outage, timeout, retry, duplicate submission, stale worker, restart and recovery
   behavior. Confirm backup/restore procedures for the chosen target.
10. Verify no credentials or personal/business data leak into logs, browser storage, artifacts or
    public responses.
11. Complete an adversarial review across kernel, API, persistence, integrations, public intake,
    operator UX, cost/quota limits, recovery and the selected deployment target.
12. Update Manifest, Roadmap and Development State with the exact verified HEAD and evidence.
13. Obtain full release-gate CI on the final commit and explicit acceptance before production.

## Current known blockers

- The current `main` production entrypoint calls `create_app(enable_docs=False)` without an
  `APIApplication` composition. The API deliberately fails closed for capabilities that are not
  composed. A running HTTP process is therefore not proof of a functional product.
- PR #75 proposes a provider-neutral runtime composition, but is not merged. Review it against
  the current base before reusing any implementation; do not merge blindly.
- This repository does not yet contain Replit-specific runtime acceptance evidence.
- A real staging PostgreSQL instance, identity provider and bot-challenge provider must be configured
  and tested before the corresponding capabilities can be accepted.
- Outbound MAX, live registry automation and production AI must remain disabled unless their own
  provider safety and activation gates pass.

## Rollback and operations

- Promote only a reviewed immutable commit.
- Keep schema changes backward-compatible with the previous application revision where possible.
- Test rollback with the actual Replit deployment mechanism and database state; reverting application
  code alone does not reverse a database migration.
- Define an operator-owned backup retention and restore schedule before production.
- Record release commit, migration version, CI run, smoke/E2E results and rollback evidence.

**Decision:** this commit adds the deployment contract and configuration foundation only.
It does not authorize production deployment or claim the website/operator/lead-search product is
fully functional.

# СХЕМА Business Platform

Commercial Intelligence & Execution OS.

## v1.5

The repository contains the approved v1.4 kernel and its integration boundaries.

Current foundation:
- domain rules are isolated from application and adapters;
- PostgreSQL is the transactional authority;
- critical command paths are identity-, policy- and evidence-gated;
- idempotency, audit, evidence, outbox, durable jobs and bounded retry contracts are first-class;
- research and AI execution have explicit gateway and budget boundaries;
- MAX is a communication adapter and produces canonical events;
- Web/PWA/Android clients do not access persistence directly;
- architecture is represented both as documentation and a machine-readable contract.

Unified v1.5 runtime controls:
- provider-neutral OIDC/JWT authentication with HTTPS-only issuer/JWKS, explicit asymmetric algorithm allow-list, issuer/audience/expiry verification, bounded JWKS caching and fail-closed permission materialization;
- production runtime security fails closed on unsafe documentation exposure, OIDC endpoints and development database defaults;
- HTTP telemetry is observational, correlation-aware and allow-list redacted; request bodies and authorization headers are excluded;
- pip-audit is a release-gated supply-chain check;
- the release contract validates the frozen v1.4 kernel and additive v1.5 maturity boundary.

Development:
Open the repository in GitHub Codespaces. The dev container installs the project and development dependencies.

Run:
ruff check .
python -m compileall -q src tests
pytest

Architecture baseline: ARCHITECTURE.md
Kernel workstream: docs/V1.4_KERNEL.md
Kernel checkpoint: docs/V1.4_KERNEL_CHECKPOINT.md
Machine-readable contract: architecture/contract.json
Runtime contract: architecture/runtime_contract.json
Database foundation migration: db/migrations/0001_foundation.sql

Durable execution plane: docs/V1.4_EXECUTION_PLANE.md

Development manifesto: docs/DEVELOPMENT_MANIFEST.md
Current maturity stage: v1.5 Core Maturity Integration & Certification
Core completion boundary: after certification, core semantics are frozen; new capabilities stay outside the kernel unless a proven invariant, security/data-integrity, or fundamental scalability/reliability defect requires change.

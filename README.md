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

v1.5 runtime progress:
- provider-neutral OIDC/JWT authentication adapter with HTTPS-only issuer/JWKS, asymmetric algorithm allow-list, issuer/audience validation, bounded JWKS caching and explicit IAM permission materialization;
- the frozen v1.4 architecture contract remains unchanged; runtime-specific controls live in the v1.5 runtime boundary.

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

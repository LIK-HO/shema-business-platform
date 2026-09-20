# СХЕМА Business Platform

Commercial Intelligence & Execution OS.

## v1.4

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
Database foundation migration: db/migrations/0001_foundation.sql

Durable execution plane: docs/V1.4_EXECUTION_PLANE.md

## v1.5 Runtime Core

The first v1.5 runtime increment adds a provider-neutral JWT/JWKS authentication boundary. See docs/V1.5_RUNTIME.md.

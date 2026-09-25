# P39 — AI Production Promotion Release Gate

P39 is the final bounded checkpoint before any future production activation decision for the approved AI providers.

## What P39 proves

The gate verifies, from the repository state:

- the frozen AI kernel is byte-identical to its certified Git blob fingerprint;
- the frozen kernel contract remains v1.4;
- the certified v1.5 core maturity contract still asserts semantic freeze;
- only YandexGPT and GigaChat are approved;
- automatic provider fallback is disabled;
- automatic production activation is disabled;
- HTTP clients cannot select the provider;
- YandexGPT and GigaChat credentials/tokens remain runtime-only;
- deterministic end-to-end evidence contains no live provider traffic;
- recovery/PITR, supply-chain and release-contract evidence references still exist;
- the canonical release contract validates successfully;
- observability remains redacted.

## Operator approval

An `AIPromotionApprovalRecord` can be created only after the assessment is promotable.

The record:

- contains operator, reason, timestamp and evidence references;
- contains no credential;
- is not persisted by P39;
- does not activate a provider;
- does not deploy or merge anything.

This deliberately keeps human approval separate from runtime activation.

## Existing CI evidence remains authoritative

P39 does not duplicate the expensive recovery or dependency-audit jobs.

Instead it binds the existing evidence sources:

- `backup-recovery` → `scripts/postgres_pitr_drill.sh`;
- `supply-chain` → `.github/workflows/ci.yml`;
- `release-contract` → `src/shema_platform/platform/release.py`.

The full CI pipeline remains the execution mechanism that proves those controls.

## Scope stop

P39 does not add:

- a provider;
- a runtime fallback;
- an HTTP route;
- a database migration;
- a new telemetry backend;
- automatic production activation;
- live provider traffic.

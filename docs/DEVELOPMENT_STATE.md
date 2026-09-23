# Development State Ledger

## Current verified context

- Repository: `LIK-HO/shema-business-platform`
- Branch: `v1.5/core-maturity`
- Base: `v1.5-runtime`
- PR: #8
- Kernel: v1.4 frozen
- Runtime: v1.5.0
- Development stage: v1.5 Core Maturity Integration & Certification

## Completed certification sub-elements

### B1 — GREEN CI — CLOSED / VERIFIED

Integrity evidence:
- CI run #970 (`35763575234`) completed successfully.
- All required quality, integration and release-contract jobs passed.
- The migration integration failure was isolated to the test helper losing `search_path` after rollback; the helper was corrected by committing schema selection before transactional assertions.
- No kernel semantics were changed to obtain the green result.

### B2 — UNIFIED v1.5 CANDIDATE — CLOSED / VERIFIED

Integrity boundary satisfied:
- PR #8 now carries the unified v1.5 runtime baseline across core maturity, production IAM and production security/telemetry/supply-chain controls.
- Frozen v1.4 architecture/domain semantics were preserved.
- Canonical OIDC/JWT authentication is provider-neutral at the IAM adapter boundary; issuer/audience/expiry/HTTPS, explicit asymmetric algorithms, bounded JWKS caching and fail-closed permission materialization are enforced.
- Production runtime security fails closed on unsafe configuration.
- Telemetry is non-authoritative, correlation-aware and allow-list redacted; authorization headers and request bodies are excluded.
- Dependency security auditing is a release gate.
- The security audit found pytest `8.4.2` affected by `PYSEC-2026-1845`; the development constraint was raised to `pytest>=9.0.3,<10`.
- CI run #989 (`35839625074`) completed successfully against PR #8 head `d2ad09033331683f00bbc73a3a74a1a92ef976af`.
- All six jobs passed:
  - quality (3.12)
  - quality (3.13)
  - integration (3.12)
  - integration (3.13)
  - supply-chain
  - release-contract
- At closure PR #8 was open, unmerged, draft and mergeable.
- No v1.4 kernel semantic changes were introduced for B2.

## Current active element

**CM-CERTIFICATION**

### Active certification sub-element

**B3 — MIGRATION ADOPTION PROOF**

Integrity boundary:
- prove a controlled adoption path for an existing v1.4 database into the current checksummed migration ledger;
- preserve existing data and schema semantics;
- prevent silent reapplication or historical migration drift;
- keep PostgreSQL as the sole transactional authority;
- do not broaden migration scope beyond adoption safety.

### Not yet closed

- B3 — Migration adoption proof
- B4 — Crash-after-external-effect integration proof
- B5 — Backup/Restore/PITR and measured RTO/RPO
- B6 — End-to-end observability correlation proof
- B7 — Security certification matrix
- B8 — SLO/error-budget baseline
- B9 — Capacity/overload baseline
- B10 — Controlled release candidate and final semantic freeze

## Exact continuation boundary

B2 is closed after live verification of PR #8 and CI run #989.

The next development action must:
1. read the current migration runner, migration ledger schema, migration baseline and existing migration integration tests;
2. compare them with the actual v1.4 schema adoption problem;
3. identify exactly one smallest safe adoption proof gap;
4. implement only that bounded change;
5. add negative/concurrency/data-preservation tests as applicable;
6. run the relevant migration/integration/release verification;
7. update this ledger.

Until B3 closes, do not start B4-B10 implementation.

## Safe next action

Establish the live B3 baseline for existing-schema adoption and select the smallest missing executable proof without changing canonical business semantics.

## Prohibited until boundary is closed

- no new kernel semantics;
- no unrelated feature work;
- no provider-driven domain changes;
- no microservice decomposition;
- no new system-of-record;
- no migration to Airtable/Replit/Bitrix24 as authority;
- no broad refactor without an explicit integrity reason;
- no starting B4-B10 ahead of B3 closure.

## Last verified repository point

- PR #8 head at B2 closure: `d2ad09033331683f00bbc73a3a74a1a92ef976af`
- CI run #989 (`35839625074`): green
- PR #8: open, unmerged, draft, mergeable
- Live GitHub branch/HEAD remains authoritative and must be re-read before continuation.

## Interruption record

If work stops during a sub-element, record:
- active sub-element;
- last verified commit;
- files changed;
- tests passed;
- tests failed/pending;
- exact unfinished operation;
- safe resume operation;
- prohibited operations.

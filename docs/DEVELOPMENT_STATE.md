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
- PR #8 carries the unified v1.5 runtime baseline across core maturity, production IAM and production security/telemetry/supply-chain controls.
- Frozen v1.4 architecture/domain semantics were preserved.
- OIDC/JWT authentication, fail-closed production security, redacted telemetry, permission materialization and dependency auditing are integrated into one runtime boundary.
- CI run #989 (`35839625074`) completed successfully against PR #8 head `d2ad09033331683f00bbc73a3a74a1a92ef976af`.
- All six jobs passed: quality 3.12/3.13, integration 3.12/3.13, supply-chain and release-contract.
- No v1.4 kernel semantic changes were introduced for B2.

### B3 — MIGRATION ADOPTION PROOF — CLOSED / VERIFIED

Integrity evidence:
- Existing v1.4 baseline is explicitly defined as migrations 0001–0008.
- `MigrationRunner.adopt_existing_schema()` verifies the required schema-owned columns before any ledger bootstrap.
- Adoption refuses a populated migration ledger and fails closed on an incomplete baseline.
- Historical migrations 0001–0008 are never re-executed during adoption.
- Ledger rows 0001–0008 are inserted transactionally with approved migration names/checksums.
- Normal `MigrationRunner.apply()` then starts from 0009.
- Integration proof preserved a sentinel record from the pre-adoption schema and completed the current plan without reapplying historical DDL.
- Integration proof also verified that an incomplete legacy schema is rejected without creating the ledger.
- CI run #996 (`35840247718`) completed successfully against PR #8 head `0e7f22f8fc164abc1fa5b121581d3f9932a606aa`.
- All six jobs passed; PostgreSQL integration on Python 3.12 reported 26 passed, 175 deselected.
- Migration adoption is now an explicit core-maturity contract property.

## Current active element

**CM-CERTIFICATION**

### Active certification sub-element

**B4 — CRASH-AFTER-EXTERNAL-EFFECT INTEGRATION PROOF**

Integrity boundary:
- prove that a successful external effect followed by process/connection loss converges to one logical effect after lease reclaim and retry;
- preserve stable external idempotency keys and canonical local truth;
- do not add new domain semantics.

### Not yet closed

- B4 — Crash-after-external-effect integration proof
- B5 — Backup/Restore/PITR and measured RTO/RPO
- B6 — End-to-end observability correlation proof
- B7 — Security certification matrix
- B8 — SLO/error-budget baseline
- B9 — Capacity/overload baseline
- B10 — Controlled release candidate and final semantic freeze

## Exact continuation boundary

B3 is closed after live verification of PR #8 and CI run #996.

The next development action must:
1. inspect the existing commercial-send/outbox recovery semantics and drills;
2. identify exactly one missing crash-after-external-effect integration proof;
3. implement only that bounded proof/test path;
4. verify stable external idempotency and one logical effect after reclaim;
5. run the relevant CI/release checks;
6. update this ledger.

Until B4 closes, do not start B5-B10 implementation.

## Safe next action

Establish the existing send-reservation/idempotency recovery path and add the smallest executable crash-after-external-effect integration proof.

## Prohibited until boundary is closed

- no new kernel semantics;
- no unrelated feature work;
- no provider-driven domain changes;
- no microservice decomposition;
- no new system-of-record;
- no migration to Airtable/Replit/Bitrix24 as authority;
- no broad refactor without an explicit integrity reason;
- no starting B5-B10 ahead of B4 closure.

## Last verified repository point

- PR #8 head at B3 closure: `0e7f22f8fc164abc1fa5b121581d3f9932a606aa`
- CI run #996 (`35840247718`): green
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

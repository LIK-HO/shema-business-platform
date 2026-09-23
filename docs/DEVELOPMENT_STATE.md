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
- CI run #970 (`35763575234`) completed successfully.
- All required quality, integration and release-contract jobs passed.
- The migration test failure was isolated to the test helper losing `search_path` after rollback; the helper was corrected without changing kernel semantics.

### B2 — UNIFIED v1.5 CANDIDATE — CLOSED / VERIFIED
- PR #8 carries the unified v1.5 runtime baseline across core maturity, production IAM and production security/telemetry/supply-chain controls.
- Frozen v1.4 architecture/domain semantics were preserved.
- CI run #989 (`35839625074`) passed all six jobs: quality 3.12/3.13, integration 3.12/3.13, supply-chain and release-contract.

### B3 — MIGRATION ADOPTION PROOF — CLOSED / VERIFIED
- Existing v1.4 baseline is migrations 0001–0008.
- `MigrationRunner.adopt_existing_schema()` verifies required schema-owned columns, refuses a populated ledger, transactionally seeds approved ledger rows 0001–0008, and leaves normal `apply()` to continue at 0009.
- Integration proof preserved a pre-adoption sentinel and rejected an incomplete legacy schema without bootstrapping the ledger.
- CI run #996 (`35840247718`) passed all six jobs; integration 3.12 reported 26 passed.

### B4 — CRASH-AFTER-EXTERNAL-EFFECT INTEGRATION PROOF — CLOSED / VERIFIED
- Added PostgreSQL integration proof for the real `CommercialActionSendWorkflow`.
- First execution durably reserves `SENDING`, the test adapter records the external effect and simulates a process crash before durable completion.
- After lease expiry, a fresh workflow instance retries with the stable `commercial-send:{action_id}` key.
- The adapter returns the same external message id instead of creating a second effect.
- Final durable state is `SENT`, send attempt is 2, idempotency result is the external id, exactly one `commercial_action.sent` outbox event and one audit record exist.
- CI run #999 (`35840734754`) completed successfully against PR #8 head `8969b29b4413acb5eac947761d13059e3ee6b543`.
- All six jobs passed; integration 3.12 reported 27 passed, 175 deselected.

## Current active element

**CM-CERTIFICATION**

### Active certification sub-element

**B5 — BACKUP / RESTORE / PITR WITH MEASURED RTO/RPO**

Integrity boundary:
- prove recoverability of PostgreSQL canonical state using a real backup/restore path;
- measure and record recovery time and recoverable-point semantics;
- prove canonical identity, commercial action, order, economics and audit data survive recovery;
- do not introduce new domain semantics.

### Not yet closed
- B5 — Backup/Restore/PITR and measured RTO/RPO
- B6 — End-to-end observability correlation proof
- B7 — Security certification matrix
- B8 — SLO/error-budget baseline
- B9 — Capacity/overload baseline
- B10 — Controlled release candidate and final semantic freeze

## Exact continuation boundary

B4 is closed after live verification of PR #8 and CI run #999.

The next development action must:
1. inspect existing PostgreSQL runtime/integration setup and recovery capabilities;
2. identify the smallest real backup/restore + measurable RTO/RPO proof;
3. implement only that bounded recovery drill;
4. verify canonical data and audit lineage after restore;
5. record measured RTO/RPO evidence and pass/fail thresholds;
6. run the relevant CI/release checks;
7. update this ledger.

Until B5 closes, do not start B6-B10 implementation.

## Safe next action

Establish the current PostgreSQL backup/restore boundary and build the smallest deterministic recovery drill that produces measurable RTO/RPO evidence.

## Prohibited until boundary is closed
- no new kernel semantics;
- no unrelated feature work;
- no provider-driven domain changes;
- no microservice decomposition;
- no new system-of-record;
- no migration to Airtable/Replit/Bitrix24 as authority;
- no broad refactor without an explicit integrity reason;
- no starting B6-B10 ahead of B5 closure.

## Last verified repository point
- PR #8 head at B4 closure: `8969b29b4413acb5eac947761d13059e3ee6b543`
- CI run #999 (`35840734754`): green
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

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

### B5 — BACKUP / RESTORE / PITR WITH MEASURED RTO/RPO — CLOSED / VERIFIED
- Added a dedicated PostgreSQL 16 physical recovery drill using `pg_basebackup`, WAL archiving and `recovery_target_time`.
- The drill restores to sentinel 1 and deliberately excludes a later sentinel 2 commit, proving point-in-time recovery rather than only logical restore.
- Canonical identity, commercial action, order, order line, economics, baseline audit and migration ledger row 0009 were present after recovery; later sentinel 2 was absent.
- Measured RTO: **2.039 seconds**.
- Measured RPO: **2.053 seconds** for the controlled drill window.
- CI run #1005 (`35841541121`) completed successfully against PR #8 head `918ad61684c89cb59531a9017343d6b326033a3d`.
- All seven jobs passed: quality 3.12/3.13, integration 3.12/3.13, supply-chain, backup-recovery and release-contract.
- The backup/recovery result is now a release-gated executable control, not only documentation.

## Current active element

**CM-CERTIFICATION**

### Active certification sub-element

**B6 — END-TO-END OBSERVABILITY CORRELATION PROOF**

Integrity boundary:
- prove correlation lineage across request/canonical API, authorization/policy, critical command, idempotency, transaction/audit and durable execution where applicable;
- ensure non-authoritative telemetry never becomes canonical truth;
- verify no request body or authorization header is emitted;
- do not add new business semantics.

### Not yet closed
- B6 — End-to-end observability correlation proof
- B7 — Security certification matrix
- B8 — SLO/error-budget baseline
- B9 — Capacity/overload baseline
- B10 — Controlled release candidate and final semantic freeze

## Exact continuation boundary

B5 is closed after live verification of PR #8 and CI run #1005.

The next development action must:
1. inspect current correlation propagation from canonical API through critical workflows and audit/telemetry;
2. identify exactly one smallest missing end-to-end observability proof;
3. implement only that bounded proof/test path;
4. verify correlation continuity and redaction;
5. run the relevant CI/release checks;
6. update this ledger.

Until B6 closes, do not start B7-B10 implementation.

## Safe next action

Establish the current correlation-id lineage across the canonical API and one critical workflow, then add the smallest executable E2E proof without changing domain semantics.

## Prohibited until boundary is closed
- no new kernel semantics;
- no unrelated feature work;
- no provider-driven domain changes;
- no microservice decomposition;
- no new system-of-record;
- no migration to Airtable/Replit/Bitrix24 as authority;
- no broad refactor without an explicit integrity reason;
- no starting B7-B10 ahead of B6 closure.

## Last verified repository point
- PR #8 head at B5 closure: `918ad61684c89cb59531a9017343d6b326033a3d`
- CI run #1005 (`35841541121`): green
- PR #8: open, unmerged, draft, mergeable
- Measured PITR RTO/RPO: 2.039s / 2.053s
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

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

### Completed certification sub-elements

**B6 — END-TO-END OBSERVABILITY CORRELATION PROOF — CLOSED / VERIFIED**

Integrity evidence:
- Added PostgreSQL integration proof for the canonical HTTP commercial-action creation path.
- `X-Correlation-Id` is accepted by the canonical API boundary and returned unchanged.
- The correlation ID reaches `RequestContext` and the real `CommercialActionCreateWorkflow`.
- The workflow persists the same correlation ID into the canonical `audit_log` row.
- Telemetry records the same correlation ID while allow-list redaction excludes authorization headers and request bodies.
- The proof passed on both Python 3.12 and 3.13 in CI run #1011 (`35842247310`).
- Backup-recovery and release-contract also passed in the same run.
- No canonical domain semantics were changed.

**B7 — SECURITY CERTIFICATION MATRIX — CLOSED / VERIFIED**

Integrity evidence:
- Security matrix `docs/SECURITY_CERTIFICATION_MATRIX.md` maps implementation, failure behavior, executable evidence and release gate for authentication, authorization, production configuration, telemetry, correlation, supply-chain, migration integrity and recovery controls.
- The matrix explicitly states that it introduces no new security semantics.
- CI run #1015 (`35842598811`) completed successfully against PR #8 and passed the relevant verification gates.

**B8 — SLO / ERROR-BUDGET BASELINE — IN PROGRESS**

Completed within B8:
- Added `architecture/slo_contract.json` with six measurable SLIs: API availability, critical mutation success, job recovery, outbox lag, external-effect completion and API latency.
- Added rolling 30-day initial SLO targets and bounded error-budget burn rules.
- Explicitly marked targets as baseline assumptions requiring recalibration from real traffic; they are not production measurements.
- Added `docs/SLO_ERROR_BUDGET.md` documenting measurement boundaries and non-authoritative telemetry semantics.
- Added `tests/test_slo_contract.py` for structural and kernel-authority validation.
- Initial CI run #1018 (`35856870994`) failed only on Ruff E501 in the new B8 test file; no test, compile, integration, recovery or release-contract failure was observed because quality stopped at lint.
- Corrected only the formatting defect; no B8 contract or kernel semantics changed.
- Fix commit: `5ae2ea7ec0d6afd555321592fb926e5c9dc3aaf4`.
- Replacement CI run #1019 (`35891354355`) is currently in progress.

## Exact continuation boundary

The next development action must remain inside B8:
1. complete CI verification for current head `5ae2ea7ec0d6afd555321592fb926e5c9dc3aaf4`;
2. if CI fails, fix only concrete B8-related defects exposed by CI;
3. if CI is green, verify the SLO contract against the active maturity manifest and release gates;
4. update this ledger to mark B8 CLOSED / VERIFIED only after the full required CI/release evidence is green;
5. do not start B9 until B8 is closed.

The B8 contract does not change frozen v1.4 kernel semantics and does not claim measured production performance.

## Safe next action

Finish verification of CI run #1019 for the B8 baseline, then close B8 only if the full required quality, integration, supply-chain, backup-recovery and release-contract gates pass.

## Prohibited until boundary is closed
- no new kernel semantics;
- no unrelated feature work;
- no provider-driven domain changes;
- no microservice decomposition;
- no new system-of-record;
- no migration to Airtable/Replit/Bitrix24 as authority;
- no broad refactor without an explicit integrity reason;
- no B9/B10 implementation.

## Last verified repository point
- Branch: `v1.5/core-maturity`
- PR #8 head: `5ae2ea7ec0d6afd555321592fb926e5c9dc3aaf4`
- CI run #1018 (`35856870994`): failed only at Ruff E501 in `tests/test_slo_contract.py`; superseded by fix commit above.
- CI run #1019 (`35891354355`): in progress; not yet sufficient to close B8.
- PR #8: open, unmerged, draft, mergeable.
- Measured PITR RTO/RPO remains 2.039s / 2.053s.
- Live GitHub branch/HEAD remains authoritative and must be re-read before continuation.

## Interruption record
If work stops during B8, resume from:
- active sub-element: B8 SLO / ERROR-BUDGET BASELINE;
- last code commit: `5ae2ea7ec0d6afd555321592fb926e5c9dc3aaf4`;
- pending verification: CI run #1019 (`35891354355`);
- changed B8 files: `architecture/slo_contract.json`, `docs/SLO_ERROR_BUDGET.md`, `tests/test_slo_contract.py`;
- safe resume operation: inspect run #1019 and perform only evidence-driven B8 fixes;
- prohibited: B9/B10 implementation, unrelated refactors, kernel semantic changes.

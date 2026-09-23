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

### B6 — END-TO-END OBSERVABILITY CORRELATION PROOF — CLOSED / VERIFIED
- Added PostgreSQL integration proof for the canonical HTTP commercial-action creation path.
- `X-Correlation-Id` is accepted by the canonical API boundary and returned unchanged.
- The correlation ID reaches `RequestContext` and the real `CommercialActionCreateWorkflow`.
- The workflow persists the same correlation ID into the canonical `audit_log` row.
- Telemetry records the same correlation ID while allow-list redaction excludes authorization headers and request bodies.
- The proof passed on both Python 3.12 and 3.13 in CI run #1011 (`35842247310`).
- Backup-recovery and release-contract also passed in the same run.
- No canonical domain semantics were changed.

### B7 — SECURITY CERTIFICATION MATRIX — CLOSED / VERIFIED
- Security matrix `docs/SECURITY_CERTIFICATION_MATRIX.md` maps implementation, failure behavior, executable evidence and release gate for authentication, authorization, production configuration, telemetry, correlation, supply-chain, migration integrity and recovery controls.
- The matrix explicitly states that it introduces no new security semantics.
- CI run #1015 (`35842598811`) completed successfully against PR #8 and passed the relevant verification gates.

### B8 — SLO / ERROR-BUDGET BASELINE — CLOSED / VERIFIED

Implementation:
- `architecture/slo_contract.json` defines six measurable SLIs: API availability, critical mutation success, job recovery, outbox lag, external-effect completion and API latency.
- All SLOs use a rolling 30-day measurement window.
- Initial targets and error-budget burn rules are explicit and bounded.
- The contract states that targets are initial baselines requiring recalibration from real traffic; they are not production measurements.
- `docs/SLO_ERROR_BUDGET.md` defines measurement boundaries and keeps telemetry observational/non-authoritative.
- `tests/test_slo_contract.py` validates the SLI set, bounded targets, error-budget calculation and the rule that SLO targets do not change kernel semantics.

Failure handling:
- CI run #1018 (`35856870994`) initially failed only on Ruff E501 in the newly added B8 test.
- The defect was corrected by formatting only; no SLO or kernel semantics changed.
- Fix commit: `5ae2ea7ec0d6afd555321592fb926e5c9dc3aaf4`.

Final verification:
- CI run #1020 (`35891436907`) passed all seven jobs on the resulting verified repository state:
  - quality 3.12 — success;
  - quality 3.13 — success;
  - integration 3.12 — success;
  - integration 3.13 — success;
  - supply-chain — success;
  - backup-recovery — success;
  - release-contract — success.
- No new instrumentation or kernel semantic changes were required; existing runtime telemetry and durable state provide the required B8 measurement signals.
- B8 is therefore CLOSED / VERIFIED.

## Current active certification sub-element

**B9 — CAPACITY / OVERLOAD BASELINE**

B9 is now the only active certification boundary before B10 release candidate.

Required scope:
1. establish bounded baseline tests for concurrent critical commands;
2. verify worker saturation and durable-job lease behavior under pressure;
3. verify retry-storm/queue-backlog behavior and bounded retries;
4. verify database contention behavior;
5. verify rate limiting or other overload protection already present;
6. verify graceful degradation without changing frozen v1.4 semantics;
7. define measurable capacity/overload acceptance criteria and executable evidence.

## Exact continuation boundary

B9 must remain bounded to capacity, overload and degradation behavior already described by the maturity manifest.

Allowed:
- executable load/stress-style tests;
- bounded test fixtures and test-only concurrency;
- measurement of queue/lease/retry/database contention behavior;
- minimal observability needed to prove existing overload behavior.

Not allowed:
- new business semantics;
- provider-driven domain changes;
- microservice decomposition;
- new system of record;
- unrelated refactors;
- changing frozen v1.4 contracts merely to make a load test pass.

B10 remains prohibited until B9 is closed.

## Safe next action

Read the live B9 maturity requirements and current runtime controls, identify the smallest missing capacity/overload proof, implement only that bounded proof, and run CI before expanding scope.

## Last verified repository point

- Branch: `v1.5/core-maturity`
- PR #8 remains open, unmerged, draft, mergeable.
- B8 verification evidence: CI #1020 (`35891436907`) fully green.
- Current state-ledger update records B8 closure and selects B9 as the next bounded element.
- Live GitHub branch/HEAD remains authoritative and must be re-read before continuing B9.

## Interruption record

If work stops during B9, resume from:
- active sub-element: B9 Capacity / Overload Baseline;
- last verified B8 evidence: CI #1020 (`35891436907`);
- safe resume operation: inspect current runtime capacity/overload controls and implement the smallest missing executable proof;
- prohibited: B10 implementation, kernel semantic expansion, unrelated refactors.

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
- `architecture/slo_contract.json` defines six measurable SLIs over a rolling 30-day window.
- Initial targets and error-budget burn rules are explicit and bounded; they are not production measurements.
- `docs/SLO_ERROR_BUDGET.md` defines measurement boundaries and non-authoritative telemetry semantics.
- `tests/test_slo_contract.py` validates contract structure and preservation of frozen kernel authority.
- CI run #1020 (`35891436907`) passed all seven jobs.
- The initial Ruff defect in CI #1018 was formatting-only and was corrected without semantic change.

### B9 — CAPACITY / OVERLOAD BASELINE — CLOSED / VERIFIED
Implementation and evidence:
- Added `architecture/capacity_overload_contract.json` with explicit acceptance criteria for concurrency, worker leases, bounded retries, queue batching, database contention, rate-limiting boundary and graceful degradation.
- Added `docs/CAPACITY_OVERLOAD.md` documenting the bounded operational model and explicitly refusing to turn unmeasured throughput into a production capacity claim.
- Added `tests/test_capacity_overload.py` covering bounded retry policy, contract integrity and 503 graceful degradation.
- Expanded the existing PostgreSQL critical-command concurrency proof from 2 concurrent workers to an 8-worker barrier-synchronized contention test using one idempotency key; the test proves one durable canonical result and matching idempotency/outbox/audit lineage.
- Existing worker reclaim/lease safety and outbox dispatch-limit tests were used as B9 evidence; no new kernel semantics were required.
- Distributed ingress rate limiting remains outside frozen core and is not invented without a measured traffic requirement.

Verification:
- CI run #1027 (`35891994690`) completed successfully with all seven jobs green:
  - quality 3.12 — success;
  - quality 3.13 — success;
  - integration 3.12 — success;
  - integration 3.13 — success;
  - supply-chain — success;
  - backup-recovery — success;
  - release-contract — success.
- B9 is therefore CLOSED / VERIFIED.

## Current active certification sub-element

**B10 — CONTROLLED RELEASE CANDIDATE / FINAL CORE SEMANTIC FREEZE**

B10 is the final certification boundary. It is not a feature-development phase.

Required scope:
1. reconcile the live repository against the frozen v1.4 kernel contract and v1.5 core-maturity contract;
2. verify all B1-B9 evidence remains represented in the state ledger and release contract;
3. verify the release artifact/version metadata is deterministic and consistent;
4. verify migration baseline, architecture contract, maturity gates and runtime boundaries;
5. perform one controlled release-candidate verification run;
6. record the final semantic-freeze decision and explicit post-certification change policy;
7. do not add product features, new providers, UI, or service decomposition.

B10 does not mean merging or production deployment. Merge/release actions require separate authorization.

## Exact continuation boundary

Allowed:
- release-contract hardening required to detect inconsistency;
- final certification evidence and machine-readable freeze markers;
- deterministic release-candidate validation;
- documentation/state-ledger reconciliation;
- focused regression checks for the final frozen boundary.

Not allowed:
- new business semantics;
- new provider integrations;
- microservice decomposition;
- new system of record;
- broad refactors;
- production deployment or PR merge without explicit authorization.

## Safe next action

Read the live release contract, v1.4 architecture contract, core-maturity contract and current PR/HEAD; identify the smallest missing B10 release-candidate proof and implement only that bounded proof.

## Last verified repository point

- Branch: `v1.5/core-maturity`
- B9 verification evidence: CI #1027 (`35891994690`) fully green.
- Current PR #8 remains open and unmerged.
- This ledger update advances the active cursor from B9 to B10.
- Live GitHub branch/HEAD remains authoritative and must be re-read before continuing B10.

## Interruption record

If work stops during B10, resume from:
- active sub-element: B10 Controlled Release Candidate / Final Core Semantic Freeze;
- last verified B9 evidence: CI #1027 (`35891994690`);
- safe resume operation: inspect release-contract/freeze evidence and implement only the smallest missing final-certification proof;
- prohibited: merge, deployment, product expansion, provider-driven domain changes, unrelated refactors.

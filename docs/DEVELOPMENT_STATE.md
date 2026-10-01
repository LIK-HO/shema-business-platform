# Development State Ledger
## Current development-session synchronization — 2026-09-27

- Branch: `v1.5/p46-max-provider-evidence-hold`
- HEAD: resolved live from GitHub; this ledger does not store a static commit pointer.
- PR: #56 — open, draft, mergeable.
- Phase 2-H lookup→retry→evidence composition and synchronized documentation are CLOSED / VERIFIED by full CI #1383 (`36315401510`) with all seven release-gate jobs GREEN.
- Phase 2-H controlled activation operation: **CLOSED / VERIFIED by CI #1392 (`36316219807`) on `de99fd3e30514c140464947099a03fa9399809f9`.**
- Phase 2-H runtime activation rehearsal: **CLOSED / VERIFIED by CI #1397 (`36316599417`) on `c47c9b7368abd5de8488390d47f212884f5eb3cc`.**
- Phase 2-H provider lookup → Evidence runtime vertical slice: **CLOSED / VERIFIED by CI #1402 (`36317002134`) on `88dab9aa995c70217af0b616d59039f62450bb26`.**
- Phase 2-H Runtime Negative Provider Outcomes & Recovery: **CLOSED / VERIFIED by full CI #1404 (`36317178100`) on `758690225996c1c2cca95cbbd3b1c56638d69db8`; live activation remains OFF.**
- Phase 2-G FNS evidence hold remains independently BLOCKED for automation.
- Implemented activation artifacts: `src/shema_platform/adapters/intelligence/dadata_activation.py`, `src/shema_platform/application/counterparty_provider_activation.py`, `architecture/dadata_activation_operation_contract.json`, `tests/test_counterparty_provider_activation.py`, plus API models/routes and canonical OpenAPI updates.
- Activation invariant: construction and startup do not activate DaData; the provider binding starts disabled and can only be enabled through the explicit control-plane operation.
- Authorization invariant: provider activation and rollback require dedicated permissions and explicit operator confirmation.
- Credential invariant: activation state, API DTOs, telemetry and operation contracts contain no provider secret.
- Identity invariant: `providerId` is supplied only by the route path, not duplicated in the request body.
- Rollback invariant: the kill-switch disables the binding, preserves safe historical activation metadata and makes no database schema change.
- Evidence invariant: DaData remains `trusted_secondary`; provider observations remain Evidence input and cannot promote canonical Identity.
- Network invariant: no live DaData traffic, no automatic activation, no fallback provider, no CI provider traffic and no credentials in source control.
- Final gate for controlled activation operation: full seven-job CI #1392 (`36316219807`) — all seven jobs GREEN.
- Verified negative/recovery evidence: deterministic runtime tests cover not-found, rate-limit retry/saturation, provider 5xx, transport recovery, secondary contradiction quarantine, no-fallback behavior, bounded retry delays and no partial Evidence/Identity mutation on terminal provider errors. Full seven-job CI #1404 (`36317178100`) passed GREEN.
- Stage exit invariant: no live DaData execution, provider credentials in repository, automatic fallback, FNS automation, MAX activation, DB schema change or frozen-kernel semantic change. No new active implementation boundary is opened by this closure.


## Stage closure evidence — 2026-09-27

- Negative/recovery test file: `tests/test_counterparty_provider_runtime_negative.py`.
- Exit document: `docs/RUNTIME_NEGATIVE_PROVIDER_OUTCOMES_2026_09_27.md`.
- Full seven-job release gate for the negative/recovery implementation: CI #1404 (`36317178100`) — all seven jobs GREEN.
- Final post-closure regression gate: CI #1408 (`36320629569`) on `6779e38578e35a5e8081ce8894b404c2fdfbe3de` — all seven jobs GREEN.
- Runtime boundary remains disabled by default; live DaData traffic did not occur.

## Historical core-certification baseline

- Repository: `LIK-HO/shema-business-platform`
- Branch at core certification: `v1.5/core-maturity`
- Base: `v1.5-runtime`
- PR: #8
- Kernel: v1.4 frozen
- Runtime: v1.5.0
- Development stage: **v1.5 Core Maturity Certified / Kernel Frozen**
- This subsection is historical certification evidence; current P46 state is defined above.

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
- The backup/recovery result is a release-gated executable control, not only documentation.

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
- `architecture/capacity_overload_contract.json` defines bounded acceptance criteria for concurrency, worker leases, retry storms, queue backlog, database contention, rate-limiting boundary and graceful degradation.
- `docs/CAPACITY_OVERLOAD.md` documents the behavioral baseline and explicitly avoids unmeasured throughput claims.
- `tests/test_capacity_overload.py` covers bounded retry policy, contract integrity and 503 graceful degradation.
- Existing PostgreSQL critical-command contention proof was expanded to 8 concurrent workers using one idempotency key and one durable canonical result.
- CI run #1027 (`35891994690`) passed all seven jobs.

### B10 — CONTROLLED RELEASE CANDIDATE / FINAL CORE SEMANTIC FREEZE — CLOSED / VERIFIED / FROZEN
- Added `architecture/release_candidate_contract.json` requiring B1-B9 evidence and all mandatory release-control artifacts.
- Hardened `src/shema_platform/platform/release.py` to fail closed when the release candidate, certification boundary, required control artifacts or final-freeze policy are incomplete.
- Added `tests/test_release_candidate.py` and reconciled the existing negative release-contract fixture.
- Added `docs/CORE_SEMANTIC_FREEZE.md` as the explicit post-certification change policy.
- Updated `docs/DEVELOPMENT_MANIFEST.md` to the certified/frozen status.
- CI run #1036 (`35892865534`) completed successfully on final manifest-synced HEAD `080b51aba24340c782632d56c5ce3f82b8c4cd1b`, with all seven jobs green:
  - quality 3.12 — success;
  - quality 3.13 — success;
  - integration 3.12 — success;
  - integration 3.13 — success;
  - supply-chain — success;
  - backup-recovery — success;
  - release-contract — success.
- CI #1032 exposed a Ruff import-format defect; CI #1034 exposed a release-test fixture gap; both were fixed before final certification.
- No production deployment or merge authorization is implied.

## Certification result

**v1.5 Core Maturity is now certified and the kernel is frozen.**

This means:
- v1.4 kernel semantics are the durable business/domain contract;
- v1.5 maturity/runtime controls are verified around that kernel;
- new product capabilities belong outside the kernel;
- ordinary feature work must not reopen core semantics;
- exceptional core changes require a proven invariant/security/data-integrity/fundamental reliability defect plus regression tests, impact analysis and rollback planning.

There is **no B11 core-expansion phase**.

## Post-certification operating boundary

Allowed:
- product/application workflows outside the kernel;
- concrete providers and integrations behind adapters;
- Web/PWA/Android/experience layers;
- operational tuning supported by measured production evidence;
- security or reliability fixes meeting the documented exception rule.

Prohibited:
- broadening the kernel for convenience;
- provider-specific domain semantics;
- new system-of-record dependencies;
- microservice decomposition without a measured constraint;
- merge or production deployment without explicit authorization.

## P46 — EXTERNAL PROVIDER BLOCKER HOLD / EVIDENCE REVALIDATION

- Status: **CLOSED / VERIFIED — external readiness remains BLOCKED**.
- Branch: `v1.5/p46-max-provider-evidence-hold`.
- P45 baseline: `e6fcaf719cadbf1bf5c57f2286babcf41128fbfd`.
- Completed boundary: authoritative revalidation of the current MAX `POST /messages` contract, message retrieval contract and official OpenAPI snapshot, with no live provider traffic.
- Verified result: send method, returned message identity, message-by-ID retrieval and rate-limit documentation remain present.
- Unresolved blockers remain unchanged: provider-side idempotency and provider-side reconciliation by client operation key remain **undocumented/unverified** in the checked authoritative artifacts.
- Final verified commit: `b4c404404b7d0cf9317caf765723a3bc2003cd46`.
- GitHub CI run #1265 (`36283673042`) completed successfully with all seven jobs green: quality 3.12/3.13, integration 3.12/3.13, supply-chain, backup-recovery and release-contract.
- P46 test correction was formatting-only: one extra blank line was removed from `tests/test_p46_max_provider_evidence_hold.py`; no production code, database schema, API semantics or frozen-kernel semantics changed.
- No live MAX traffic, provider credentials or production activation occurred.
- Phase 0 exit criteria are satisfied. The next selected capability is **Phase 1 — Intelligence Quality Foundation**; implementation is not yet started.
- Manifest, roadmap, P46 contract and branch state must remain synchronized before Phase 1 implementation begins.
- Prohibited until blocker closure: live MAX outbound activation, automatic live retry, compensating provider/fallback, provider-specific production execution, database migration and frozen-kernel semantic changes.
- Source contract: `architecture/max_provider_evidence_revalidation_contract.json`.
- Operator documentation: `docs/P46_MAX_PROVIDER_EVIDENCE_HOLD.md`.
- Executable evidence: `tests/test_p46_max_provider_evidence_hold.py`.

## Last verified repository point

- Branch: `v1.5/core-maturity`
- HEAD: `080b51aba24340c782632d56c5ce3f82b8c4cd1b`
- PR #8: open, unmerged, draft.
- Final certification evidence: CI #1036 (`35892865534`) fully green.
- v1.4 kernel semantics: frozen.
- v1.5 core maturity: certified.

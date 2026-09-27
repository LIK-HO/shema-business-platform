# Development State Ledger
## Current development-session synchronization — 2026-09-27

- Branch: `v1.5/p46-max-provider-evidence-hold`
- HEAD: resolved live from GitHub for every development session; the state ledger intentionally does not self-reference its own commit SHA.
- PR: #56 — open, draft, mergeable.
- Current boundary: Phase 2-G — First Source Selection and Evidence Capture — READY / implementation not started.
- Phase 2-A implementation: bounded search-run orchestration, explicit completeness states, source/candidate budgets, deterministic source order, canonical candidate normalization and benchmark search-quality metrics.
- Phase 2-A implementation commits: cfb48dd9dbccee426403834f1e153ac4440ed11b (initial slice) and a94573ad8c5ab83b6f44ceb5281b9f7c9d045182 (test-contract correction).
- Phase 2-A verification: CLOSED / VERIFIED by full CI #1316 (36304414654) on HEAD af813ff79802aa358eafcb68586d3bf0b105aa7d; supply-chain, quality 3.12/3.13, integration 3.12/3.13, backup-recovery and release-contract all passed.
- Phase 2-B scope: validate registry source references, reliability/access metadata and lawful-access policy before a source enters a search plan; no network automation or ranking authority. CLOSED / VERIFIED.
- Phase 2-B verification: CLOSED / VERIFIED by full CI #1324 (36308069460) on HEAD ee549cada95a0a90a7647b2b01eec51fa0bdd9bc; all seven release-gate jobs passed.
- CI #1314 and #1315 were cancelled by GitHub concurrency after the corrected run was superseded; they are not authoritative verification evidence.
- No database schema, network automation, ranking authority, automatic qualification, canonical identity semantic change, MAX activation or frozen-kernel change was introduced in Phase 2-A or Phase 2-B.
- Phase 2-C implementation: registry-backed operator search composition over the existing API/application boundary; injected non-network adapters only; explicit completeness, plan version and source provenance returned to the operator.
- Phase 2-C closure: the API/application composition is verified; it intentionally remains provider-neutral and is not yet wired into the provider-specific runtime composition.
- Phase 2-C verification: CLOSED / VERIFIED by full CI #1330 (36308647549) on HEAD 16c08111e025bd267787eaa5de36c4dd53f70609; all seven release-gate jobs passed.
- Phase 2-D implementation: provider-neutral SearchAugmentedAPIApplication composes the verified search capability with the existing runtime API application; existing AI/provider lifecycle remains unchanged.
- Phase 2-D closure: CLOSED / VERIFIED.
- Phase 2-D verification: full CI #1336 (`36309294705`) on HEAD `7637871b3cac379fdff056aed90ddc73aacf760f`; all seven release-gate jobs passed.
- Phase 2-D evidence: provider-neutral SearchAugmentedAPIApplication, real runtime HTTP `/v1/search` smoke through the composition root, existing AI/provider lifecycle preservation, and existing API behavior preservation.
- Phase 2-E selected boundary: define and enforce the compliance contract between registry-declared sources and provider adapters, with network activation remaining disabled.
- Safest next action: implement the smallest adapter-compliance contract and deterministic negative-path tests; no live provider traffic.
- P46 MAX provider evidence hold: CLOSED / VERIFIED.
- Phase 1-A implementation is bounded to application service, canonical API adapter, OpenAPI contract and tests; no external provider automation is enabled.
- Frozen kernel: unchanged.
- No database schema, canonical identity semantics, MAX activation or external network execution was introduced.
- Verified Phase 1-A implementation commit: `363eb19043e280585fae1d3a2e7c78e2d387ab02`.
- Verification CI: run #1297 (`36284386157`) — all seven required jobs passed.
- Phase 1-A completed sub-boundaries: authoritative-source validation, INN/OGRN/OGRNIP observation contract, identity resolution by tax ID when available, traceable evidence, freshness, contradiction quarantine, append-only audit, compact operator brief, API/OpenAPI boundary.
- Phase 1-A exit: full CI/release verification passed; frozen kernel unchanged; no database migration or external FNS network execution introduced.
- Phase 1-B entry synchronization and integrity boundary: completed.
- Phase 1-B is CLOSED / VERIFIED; the active boundary is now Phase 2 and no Phase 2 implementation has started.
- Phase 1-B implementation complete: source registry contract, ten-case synthetic benchmark corpus, pure resolution/quality metric evaluator, operator documentation and negative-path tests.
- Phase 1-B verification complete: CI run #1307 (`36302695693`) on `6172bb4dfd2fda1d75a766368bf669ce1e57ed39`; all seven required jobs passed.
- Phase 1-B exit: no database schema, network automation, canonical identity semantic change or frozen-kernel change.
- Phase 2-E implementation: adapter descriptor, registry-metadata compliance validator, canonical SearchSource binding and negative-path tests; network execution remains disabled. CLOSED / VERIFIED.
- Historical Phase 1-B guardrail: mass source integration, hidden ranking gates, automatic qualification/promotion, new source-of-truth tables, kernel semantic changes, provider activation and MAX changes were prohibited until the benchmark boundary was closed.
- Current Phase 2 guardrail: do not broaden into mass source orchestration or ranking authority before the smallest search/research vertical slice is contracted and measured.
- Prior P46 full CI verification remains run #1265 (`36283673042`) on commit `b4c404404b7d0cf9317caf765723a3bc2003cd46`; all seven required jobs passed.


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

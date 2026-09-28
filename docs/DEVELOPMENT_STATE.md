# Development State Ledger
## Current development-session synchronization — 2026-09-28

- Branch: `v1.5/p47-product-expansion`.
- HEAD: resolved live from GitHub; this ledger does not store a static commit pointer.
- PR: #58 — open, draft, mergeable state subject to current CI; head resolved live.
- Phase 2-H Runtime Negative Provider Outcomes & Recovery: CLOSED / VERIFIED; live DaData remains OFF.
- Current verified architecture boundary: **Public Intake Trust Boundary + Counterparty Preflight + Platform Evolution Contract** — CLOSED / VERIFIED at contract and test stage. Runtime public-form implementation remains governed by the Phase 3B roadmap exit criteria.
- Current active extension: **Operator Interface Alignment + Repeat Orders & Business Continuity + Public Intake + Counterparty Monitoring + Bitrix24 Cutover** — contract/test work in progress until the final current-head adversarial review and release gate close.
- Previous draft procurement subsystem removed from the current product boundary; no procurement/tender runtime, provider adapters, tender workspace or procurement persistence remains in the active implementation.
- Product flow is fixed for the initial B2B stage as: intelligence → identity/evidence → qualification → contact preparation → repeat orders/business continuity → business handoff → live business execution → result/learning.
- Phase 3A is fixed as Repeat Orders & Business Continuity in temporary Shema live mode, with verified Bitrix24 cutover and purge/hide semantics.
- Phase 4 is the unified Web operator/public-client surface; no internal document-management subsystem is part of the roadmap.
- Web + PWA are the only approved experience surfaces; Android is removed from the target roadmap.
- Multi-operator collaboration is a permanent architecture requirement: explicit actor, ownership/assignment/team queues, server-side authorization, audited handoff, revision/concurrency protection and explicit conflict resolution.
- Public experience boundary: схемагрупп.рф is the target public Web/PWA domain; the same public request application is projected into a MAX mini-app, with request/correlation/source attribution preserved.
- Prohibited until the explicitly selected next boundary: frozen-kernel semantics, unrelated UI work, FNS automation, MAX activation, provider fallback and unbounded crawling.

## Adversarial regression synchronization — 2026-09-28

- Added explicit `architecture/business_plane_boundary_contract.json` for Shema → Bitrix24 handoff, field ownership, retry/reconciliation and outcome return.
- Corrected YandexGPT configuration so `YANDEXGPT_MAX_COST` is explicitly required and positive; zero/missing cost ceilings now fail closed.
- The earlier Repeat Business Preparation wording is superseded by the bounded temporary Shema live repeat-order mode; Shema still must not reimplement Bitrix24's recurring-deal engine.
- Monium is explicitly operational telemetry; durable audit/business history remains PostgreSQL-owned.
- Full seven-job release-gate CI for the current verified HEAD d595ec856a6a611751c7b619ae75f23ca3db4398 is GREEN in run 36372953967; all quality, integration, supply-chain, backup/recovery and release-contract jobs passed.
- Global adversarial survivability gate is now mandatory for every material strategy change and every element completion; no element may enter VERIFIED/CLOSED without a current-head whole-system adversarial review.
- Data-plane rule: Managed PostgreSQL remains the canonical Shema database in Yandex Cloud. Bitrix24 receives live business ownership after handoff; the Shema database is not wholesale migrated into Bitrix24.
- Operator continuity rule: every business handoff carries stable Shema identity, handoff, correlation and Bitrix entity references so one or multiple operators can reconstruct the full causal chain without shadow copies.

## Strategic boundary synchronization — 2026-09-28

- A new Yandex Cloud deployment strategy is recorded: Serverless Containers + API Gateway + narrow Cloud Functions/Timers + Lockbox + Container Registry + Object Storage + Monium, with Managed PostgreSQL remaining the canonical production database.
- Bitrix24 is established as the future mature business control plane for live transactions, pricing, calculations/economics, communications, assignments and process automation. Shema supplies verified context and later receives minimal outcome signals for learning.
- New Shema development must not expand into a second CRM, accounting, finance or personnel system. Existing frozen Order/Economics semantics remain only for compatibility, lineage and learning.
- Existing YandexGPT and MAX provider boundaries remain in force. YandexGPT is the bounded AI processing path; MAX live outbound remains fail-closed until provider-side idempotency or deterministic reconciliation is evidenced.
- This synchronization is architecture/experience-contract/test scope only. No Bitrix24 runtime, MAX activation or new persistence authority has been opened.
- New strategy contracts: architecture/platform_growth_strategy_contract.json, architecture/business_plane_boundary_contract.json, architecture/public_client_experience_contract.json and architecture/operator_interface_contract.json.
- New executable guards: tests/test_platform_growth_strategy_contract.py, tests/test_business_plane_boundary_contract.py and tests/test_public_client_experience_contract.py.
- Adversarial review: docs/ADVERSARIAL_ARCHITECTURE_REVIEW_2026_09_28.md.
- Operator interface blueprint: architecture/operator_interface_contract.json.

## Stage verification — 2026-09-28

- Full seven-job release gate: CI #1417 (`36351981305`) — GREEN.
- Quality 3.12: success.
- Quality 3.13: success.
- Supply-chain: success.
- Integration 3.12: success.
- Integration 3.13: success.
- Backup/recovery: success.
- Release-contract: success.

## Current strategy-boundary verification — 2026-09-28

- Boundary: **Public Intake Trust Boundary + Counterparty Preflight + Platform Evolution Contract**.
- Current verified HEAD: d595ec856a6a611751c7b619ae75f23ca3db4398.
- Full CI run 36372953967 passed all seven jobs: quality 3.12/3.13, integration 3.12/3.13, supply-chain, backup-recovery and release-contract.
- Dedicated contract tests were added for public intake and controlled platform evolution.
- During verification, the gate exposed and the branch corrected two regressions: YandexGPT dataclass field ordering and a stale Bitrix24 business-plane ownership assertion.
- No FNS live automation, public-form Bitrix24 write path, or MAX activation was opened by this stage.
- The verified result closes the architectural contract/test stage; runtime implementation must still satisfy the Phase 3B exit criteria before production activation.

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
- Web/PWA/experience layers;
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

- Verified strategy boundary: **Public Intake Trust Boundary + Counterparty Preflight + Platform Evolution Contract** — CLOSED / VERIFIED at contract/test stage.
- Deterministic registry preflight is the first line: GPT is not used for INN/OGRN validation or registry truth lookup.
- Public form is untrusted ingress; layered edge/application protection, idempotency, anti-enumeration and provider budgets are mandatory.
- No live FNS automation or public-form Bitrix24 write path is activated by this contract change.
- Adversarial review of the delta found no new kernel authority or cross-system split-brain. The current-head full release-gate CI is GREEN; production activation remains separately gated.
## Current strategy extension — 2026-09-28

- New active boundary: **Repeat Orders & Business Continuity + Public Intake Data Plane + Counterparty Monitoring + Bitrix24 Transaction Cutover**.
- Public client submissions now have a separate dedicated PostgreSQL intake database boundary; raw intake is not written directly into the canonical Shema database.
- Shema provides temporary live repeat-order execution until the Bitrix24 business plane is active. The frozen Order/Economics kernel is reused without semantic expansion.
- Bitrix24 cutover is destructive only after complete package transfer, readback verification, recovery snapshot verification and reconciliation proof. Live Shema Order/Economics rows are then purgeable and the operator UI hides those capabilities cleanly.
- Counterparty monitoring is a separate operator workspace with daily deterministic registry change detection, severity-aware notifications and personal favorites.
- The adversarial gate has been extended to intake loss/notification recovery, transaction migration completeness and monitoring false-positive/poisoning scenarios.
- Runtime implementation remains gated by contracts, negative paths, integration/E2E, recovery, adversarial review and current-head CI.

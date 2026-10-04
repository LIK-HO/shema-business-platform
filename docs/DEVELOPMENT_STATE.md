# Phase 7 — Yandex Cloud Production Foundation — IN_PROGRESS (2026-10-04)

- Closed sub-boundary: Phase 7B — Production runtime/artifact composition — CLOSED / VERIFIED.
- Active boundary: Phase 7C — Cloud resource provisioning + live evidence — IN_PROGRESS.
- Mature baseline branch: phase7c/yandex-cloud-mature-baseline-20261004.
- Current implementation HEAD: 4fb39aeb89058f58f65ad344164dac1a42cab816.
- Draft PR: #69 — Phase 7C: align Yandex Cloud deployment with mature production baseline.
- Repository release gate before this final documentation-only delta: CI run 37224391371 — 7/7 GREEN on the preceding implementation HEAD.
- Terraform IaC gate: green on the preceding implementation HEAD.
- Mature baseline: deployment and Terraform-state identities are separated; remote Object Storage state uses dedicated S3 credentials, versioning and S3 lockfile; runtime/audit log groups are explicit; Audit Trails is provisioned; Container Registry vulnerability scanning is enabled on push and scheduled rescan; optional custom-domain binding fails closed without a Certificate Manager certificate.
- Audit Trail delivery identity uses logging.writer on the destination log group and audit-trails.viewer on the collection scope.
- Runtime architecture: Serverless Containers + API Gateway + Managed PostgreSQL + Lockbox + Container Registry + Object Storage; Kubernetes is intentionally not introduced without a measured scaling/operational requirement.
- Data authority: Managed PostgreSQL remains the single transactional authority; current HA baseline is two hosts in separate availability zones; no public PostgreSQL ingress.
- Recovery boundary: private same-VPC task-mode migration/evidence runner, protected rollback drill and separate-cluster PITR are implemented in the protected workflow.
- Observability lifecycle: current Terraform-supported path is Yandex Cloud Logging; Monium is the required migration target before the Cloud Logging retirement window. No unsupported Monium integration is claimed.
- Repository-side maturity contract: docs/YANDEX_CLOUD_MATURE_PRODUCTION_BASELINE.md.
- Operational runbook: docs/PHASE7C_PRODUCTION_RUNBOOK.md.
- Live evidence contract: architecture/phase7c_live_evidence_contract.json.
- Real cloud state: NOT CLAIMED until the protected Yandex provisioning/evidence workflow executes successfully against the exact current implementation HEAD.
- Remaining 7C closure blockers: real state-bucket access through the dedicated state credentials; successful Terraform init/plan/apply; live infrastructure/database/Lockbox/API Gateway evidence; runtime/audit observability evidence; budget evidence; production smoke; live rollback; live PITR + cleanup; final live adversarial review; and the final current-head seven-job gate on this exact final HEAD.
- Verified historical blocker: the previous production run failed at state-bucket access with Yandex PermissionDenied / Access Denied while using the deployment service-account identity. The workflow is now corrected so state preflight uses the dedicated Terraform-state credentials.
- Closure rule: Phase 7C remains IN_PROGRESS until every required live-evidence item in architecture/phase7c_live_evidence_contract.json is attached to the exact deployed HEAD and the final current-head seven-job gate remains GREEN.

# Phase 6 Web/PWA Consolidation — CLOSED / VERIFIED (2026-09-30)

- **Boundary:** Phase 6 — Production Web/PWA Consolidation.
- **Implementation HEAD:** `1b75bfb46f73309597420b4e1b7762c1477a1e8c`.
- **Acceptance:** `tests/test_phase6_operator_consolidation_acceptance.py`.
- **Full release gate:** CI `36637312890` — **7/7 GREEN** (quality 3.12/3.13, integration 3.12/3.13, supply-chain, backup/recovery, release-contract).
- **Adversarial review:** completed over the full approved architecture. Findings fixed: operator route fails closed after capability rejection; handoff state is explicitly `NOT_COMPOSED` and cannot imply external acknowledgement/success.
- **Experience contract:** one Web/PWA surface, canonical API/domain semantics, server-authoritative capability visibility, explicit causal/context links, memory-only personal view state and no second business store/rule layer.
- **Frozen kernel:** unchanged.
- **PR #62:** open / draft / unmerged.
- **Next active boundary:** Phase 7 — Yandex Cloud Production Foundation.

# Phase 5 PWA — CLOSED / VERIFIED (2026-09-30)

- **Boundary:** Phase 5 — PWA.
- **Implementation HEAD:** `337b3c3f8465b406d13f6655f8e65910efe4524a`.
- **Acceptance:** `tests/test_phase5_pwa_acceptance.py`.
- **Security invariant:** SI-26.
- **Full release gate:** CI `36635383440` — **7/7 GREEN** (quality 3.12/3.13, integration 3.12/3.13, supply-chain, backup/recovery, release-contract).
- **Global adversarial review:** completed on the full approved architecture. One trust-boundary defect was found in review: root PWA bootstrap routes required explicit unauthenticated allowlisting. Fixed in `src/shema_platform/experience/api.py` and covered by an HTTP-level acceptance test. No P0/P1 findings remain open.
- **Safety properties:** public-only service-worker cache; business APIs/protected state network-only; pending public mutations are bounded and memory-only, require Idempotency-Key, reject Authorization-bearing entries, and fail closed on conflicts.
- **Frozen kernel:** unchanged.
- **Next active boundary:** Phase 6 — Production Web/PWA Consolidation.
- **PR #61:** open / draft / unmerged.

# Phase 5 PWA — IN_PROGRESS (2026-09-30)

- **Boundary:** Phase 5 — PWA.
- **Sub-boundaries:** installability; service-worker lifecycle; public-only offline shell cache; bounded memory-only pending mutation queue; reconnect/conflict handling; safe update/rollback behavior.
- **Base:** Phase 4 final synchronized HEAD `853280bc96307a8e5023b8f65dbc8de667f5c5cb`.
- **Current branch:** `phase5/pwa-20260930`.
- **Implementation contract:** `architecture/pwa_contract.json`.
- **Acceptance contract:** `tests/test_phase5_pwa_acceptance.py`.
- **Invariant:** SI-26 — PWA offline/cache layer cannot become business authority.
- **Status:** implementation in progress; closure blocked until targeted tests, global adversarial review, documentation synchronization and full seven-job release gate pass on final HEAD.

# Phase 4 global acceptance — CLOSED / VERIFIED (2026-09-29)

- **Phase:** Phase 4 — Web Operator System.
- **4A:** CLOSED / VERIFIED.
- **4B:** CLOSED / VERIFIED.
- **4C:** CLOSED / VERIFIED.
- **4D:** CLOSED / VERIFIED.
- **4E:** CLOSED / VERIFIED.
- Final global acceptance runtime HEAD: `13de9b974bf59070dfbe2f4cd69f5ec7255c42f4`.
- Final global acceptance full seven-job gate: `36588002294` — **7/7 GREEN**.
- No runtime code changes were made after that gate; the present synchronization commit is documentation/security-contract only.
- Final global acceptance contract: `tests/test_phase4_global_acceptance.py`.
- **PR #60:** open / draft / unmerged.
- **PR #59:** open / draft / unmerged; untouched by Phase 4 work.

# Current Phase 4-4D closure — 2026-09-29

- **Boundary:** Phase 4-4D — Repeat Orders & Business Continuity Web boundary.
- **Status:** **CLOSED / VERIFIED** on exact implementation HEAD `f28a8323e2f7b68311df8dbb9f83402fad3a3821` by full seven-job CI run `36584780497`.
- Implemented: authenticated repeat-plan create/next/confirm/pause/resume/skip/cancel/context-edit API surface, idempotency-bound command handling, capability-gated Web operator workspace, and fail-closed behavior when no real server-side `RepeatOrderRevalidator` is composed.
- The client never substitutes its own price/policy/date/capacity/evidence validation and never persists repeat-order business truth locally.
- Existing RepeatOrderService/domain remain canonical; Web is only an experience layer.
- Security evidence: repeat-order capability is advertised only when server-side service composition exists; absent composition returns a controlled capability-unavailable response.
- **Next active boundary:** Phase 4-4E — System/control-plane hardening and Phase 4 global acceptance.

# Current Phase 4-4B closure — 2026-09-29

- **Boundary:** Phase 4-4B — Public Client Intake + Attribution + MAX projection hardening.
- **Status:** **CLOSED / VERIFIED** on exact implementation HEAD `273333d2432abc5ce8318fe58df219ab90f06230` by full seven-job CI run `36582610189`.
- Public surface now combines company/service landing content with advanced request intake while preserving canonical API/trust-boundary semantics.
- UTM source/medium/campaign, referrer and entry surface are captured; correlation lineage is displayed server-authoritatively; MAX uses the same Web app through the same static origin.
- No public browser action creates an authoritative live order.
- **Next active boundary:** Phase 4-4C — Operator causal workbench.

# Current Phase 4-4A closure — 2026-09-29

- **Boundary:** Phase 4-4A — Canonical Web/Public + Protected Operator Shell.
- **Status:** **CLOSED / VERIFIED** on current implementation HEAD.
- Implemented: same-origin Web shell/assets, responsive operator workspace shell, server-side operator capability advertisement, protected business APIs, public request surface, MAX projection through the same static Web application.
- Security boundary: HTML/CSS/JS routes are public shell only; business APIs remain behind authentication/authorization. Operator credentials are held only in page memory; browser storage is not used.
- Contract evidence: `architecture/operator_interface_contract.json`, `architecture/public_client_experience_contract.json`, `architecture/security_invariants_contract.json`.
- Tests: Web route/assets contract tests, client-state/direct-DB negative tests, protected-operator adversarial test, visual-structure contract tests.
- **CI:** run `36581452677` — quality 3.12/3.13, integration 3.12/3.13, supply-chain, backup/PITR and release-contract all **GREEN**.
- PR #60 remains **OPEN / DRAFT / UNMERGED**. PR #59 remains untouched and **OPEN / DRAFT / UNMERGED**.
- **Next active boundary:** Phase 4-4B — Public Client Intake + Attribution + MAX projection hardening.

# Current Phase 3C-1 closure — 2026-09-29

- **Boundary:** Phase 3C-1 — Counterparty Monitoring & Favorites runtime model/persistence.
- **Status:** **CLOSED / VERIFIED** on exact implementation HEAD resolved live from GitHub.
- **Evidence:** full seven-job release-gate CI #2041 (`36561799870`) GREEN: quality 3.12/3.13, supply-chain, integration 3.12/3.13, backup/PITR and release-contract.
- **Implemented:** actor-scoped Monitoring and personal Favorites; checksum validation; idempotent commands; PostgreSQL persistence; snapshot hash/provenance; deterministic change detection; audit/outbox; protected API routes; explicit runtime composition.
- **Adversarial result:** invalid identifiers, authorization absence, cross-actor access, duplicate commands and snapshot tampering are rejected by runtime/tests. No unresolved P0/P1 found inside 3C-1 scope.
- **Next implementation boundary:** **Phase 3C-2 — Checkpointed Daily Counterparty Monitoring Worker + Provider-Outage/Recovery Semantics.**
- Full Phase 3C exit criterion remains open until 3C-2 and the contract's batch/recovery requirements are implemented and verified.


# Current Phase 3B closure — 2026-09-29

- **Boundary:** Phase 3B — Public Intake Data Plane + Trust Boundary + Counterparty Preflight.
- **Status:** **CLOSED / VERIFIED** on exact E2E implementation HEAD `254f7467e05fd92d0c594558f6a4263684040557`.
- **Evidence:** full seven-job release-gate CI #2004 (`36558811275`) GREEN: quality 3.12/3.13, supply-chain, integration 3.12/3.13, backup/PITR and release-contract.
- **E2E proof:** accepted intake survives simulated canonical Shema outage; later outbox replay reconstructs canonical request context and operator notification; replay converges without duplicate notification/projection.
- **Persistence correction:** migration 0014 creates the canonical projection/notification schema and is included in PITR recovery.
- **Adversarial result:** no unresolved P0/P1 found in the reviewed Phase 3B scope after the final E2E boundary.
- **Next implementation boundary:** Phase 3C — Counterparty Verification, Monitoring & Favorites.


# Phase 3B runtime persistence synchronization — 2026-09-29

- **Boundary:** canonical persistence required by Public Intake Data Plane.
- **Finding:** projection runtime referenced canonical tables absent from migrations 0001–0013.
- **Fix:** migration `0014_public_intake_projection.sql` creates `public_request_context` and `operator_notification`; PITR drill updated to the new canonical migration 0014.
- **Verification:** full seven-job CI #2001 (`36558318175`) is GREEN on the exact implementation HEAD before documentation synchronization.
- **Status:** persistence blocker **CLOSED / VERIFIED**. Full Phase 3B outage/replay/reconstruction exit criterion remains open until the dedicated E2E boundary is completed.


# Security re-baseline synchronization — 2026-09-29

- **Security branch:** `security/global-rebaseline-2026-09`.
- **PR:** #59 remains open and draft; merge/production authorization is not implied.
- **Current HEAD:** resolved live from GitHub; this ledger does not store a static commit pointer.
- **Security trust-chain doctrine:** untrusted input → edge/authentication → authorization → resource scope → validation → evidence provenance → policy → transaction/concurrency → external-effect reservation → external call → reconciliation → audit → recovery.
- **Implemented current security sub-boundaries:** resource-read scope (1C-READ), permission non-escalation (1C-PERM), commercial external-effect stale-worker protection (1C-EFFECT), public-intake outbox stale-worker protection (1C-OUTBOX), provider rollback CAS (1C-ACTIVATION), cached provider binding (1C-BINDING), and stale local activation-state recovery (1C-ACTIVE-STATE).
- **Current verification status:** Global Security Re-baseline is **CLOSED / VERIFIED** on exact HEAD `b8983dcf16630869db1318746edc93298ea8c333` by full seven-job release-gate CI #1994 (`36556900641`). Earlier green runs are retained only as historical evidence.
- **Latest CI sequence:** #1992 exposed two integration-test defects (provider activation SQL parameter count and public-intake outbox test database isolation); both were corrected. CI #1994 then passed all seven jobs on exact HEAD. No unresolved runtime/security defect remains in the verified security boundary.
- **Post-gate adversarial result:** read-only global scan rechecked API resource reads, public-intake rate limiting, worker lease transitions and provider activation/binding paths after CI closure; no new P0/P1 finding was identified within the approved security boundary.

## Current development-session synchronization — 2026-09-28

- **Phase 3A — Repeat Orders & Business Continuity: CLOSED / VERIFIED.**
- Exact implementation HEAD at stage verification: `7a766c35c4a2ce8a38d9fbeda268896d6716bd4e`.
- Full release-gate CI #1628 (`36402645839`) is GREEN across all seven jobs: quality 3.12/3.13, integration 3.12/3.13, supply-chain, backup/recovery and release-contract.
- Implemented bounded local repeat-order runtime over the frozen Order/Economics semantics: repeat plan lifecycle, next-order clone, mandatory pre-confirmation revalidation boundary, idempotency, audit/outbox, optimistic concurrency and transactional rollback.
- Added durable PostgreSQL repeat-plan migration `0010_repeat_order_plan.sql`; frozen kernel baseline remains unchanged.
- Added unit + PostgreSQL integration coverage for lifecycle, duplicate protection, current-price revalidation, identity safety, stale-write rejection, transaction rollback and durable lineage.
- PITR drill now verifies the current post-core schema through migration 10 while preserving the frozen migration-9 baseline semantics.
- Global adversarial review for 3A found no unresolved P0/P1 blocker inside the implemented boundary. Deferred P1s remain later Bitrix24 handoff/runtime, public Web/PWA runtime, outcome-learning runtime and MAX activation.
- **Next implementation boundary:** Phase 3B — Public Intake Data Plane + Trust Boundary + Counterparty Preflight.

- Branch: `v1.5/p47-product-expansion`.
- HEAD: resolved live from GitHub; this ledger does not store a static commit pointer.
- PR: #58 — open, draft, mergeable state subject to current CI; head resolved live.
- Phase 2-H Runtime Negative Provider Outcomes & Recovery: CLOSED / VERIFIED; live DaData remains OFF.
- Current verified architecture boundary: **Public Intake Trust Boundary + Counterparty Preflight + Platform Evolution Contract** — CLOSED / VERIFIED at contract and test stage. Runtime public-form implementation remains governed by the Phase 3B roadmap exit criteria.
- Current verified boundary: **Operator Interface Alignment + Repeat Orders & Business Continuity + Public Intake + Counterparty Monitoring + Bitrix24 Cutover strategy/contracts** — CLOSED / VERIFIED after current-head adversarial review and the final functional release-gate CI #1600 (`36397100698`). The visual Web/PWA runtime remains the separately scoped Phase 4 implementation boundary.
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
- Repeat-order boundary correction: Shema owns the bounded temporary local repeat-order mode; Bitrix24 remains the recurring-deal authority after verified cutover.
- Monium is explicitly operational telemetry; durable audit/business history remains PostgreSQL-owned.
- The functional P47 release gate CI #1600 (`36397100698`) is GREEN: quality 3.12/3.13, integration 3.12/3.13, supply-chain, backup/recovery and release-contract all pass.
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

## Current-head boundary closure — 2026-09-28

- HEAD: `6d8ca21b2a8af96cdb0b5de6c0d4aae3eb13689a`.
- PR #58: open, draft, mergeable; no merge or production authorization implied.
- Full release-gate CI #1589 (`36386211886`) is GREEN across all seven jobs: quality 3.12/3.13, integration 3.12/3.13, supply-chain, backup/recovery and release-contract.
- The preceding CI defect was a stale operator-interface assertion requiring obsolete left-navigation entries; it was corrected to match the approved model where global search lives in the header and Repeat Orders is a specialized workspace.
- Global adversarial review has no unresolved P0 finding for this boundary after the current-head gate closed. Deferred P1 items remain explicitly bounded to later roadmap stages and do not authorize new runtime authority in the current boundary.
- P47 is therefore CLOSED / VERIFIED at the architecture-and-test boundary. This does not claim that the Web/PWA visual runtime, Bitrix24 live integration, outcome-learning runtime, or MAX live outbound are implemented or activated.
- Next implementation boundary is governed by the roadmap: **Phase 3A — Repeat Orders & Business Continuity (temporary Shema live mode)**.

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
- Current-head verification: CI run #1591 (`36387246513`) on the synchronized HEAD passed all seven release-gate jobs: quality 3.12/3.13, integration 3.12/3.13, supply-chain, backup/recovery and release-contract. The earlier CI #1588 failure was an obsolete intermediate-head failure caused by the stale `search` navigation assertion and is not evidence against the current HEAD.

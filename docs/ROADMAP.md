# Shema Business Platform — Development Roadmap

## 1. Purpose

This roadmap defines the optimal post-core development strategy for Shema as a personal, scalable, reliable and durable system.

It is not a SaaS breadth roadmap.

The frozen v1.4 kernel and certified v1.5 Core Maturity remain the protected internal foundation. New capability is built outside the kernel through bounded vertical slices.

The governing product loop is:

SEARCH → INTELLIGENCE → EVIDENCE → QUALIFICATION → CONTACT PREPARATION → BUSINESS HANDOFF → ACTION → RESULT → LEARNING

The governing engineering loop is:

CONTRACT → IMPLEMENT → NEGATIVE PATHS → INTEGRATION → E2E → SECURITY/RECOVERY → CI → CLOSE → NEXT SLICE

## 2. Strategy derived from mature-system practice

The roadmap combines the following durable patterns:

- frozen/stable core with extensibility around released boundaries;
- SRE-style measurable SLOs, error budgets, supervised staged rollout and rollback;
- Well-Architected treatment of operational excellence, security, reliability, performance and cost;
- identity resolution separated from candidate discovery;
- provenance and source reliability separated from claim confidence;
- explicit ambiguous/possibly-same relationships instead of forced merges;
- reproducible releases and protected deployment environments;
- evidence-driven intelligence rather than raw information volume.

References:
- Google SRE service best practices: https://sre.google/sre-book/service-best-practices/
- Google SRE release engineering: https://sre.google/sre-book/release-engineering/
- AWS Well-Architected Framework: https://docs.aws.amazon.com/wellarchitected/latest/framework/
- OpenSanctions matching: https://www.opensanctions.org/docs/api/matching/
- OpenSanctions matching tuning: https://www.opensanctions.org/docs/api/tuning/
- Sayari entity resolution: https://documentation.sayari.com/sayari-library/entity-resolution/entity-resolution
- OpenCTI reliability/confidence: https://docs.opencti.io/latest/usage/reliability-confidence/
- FollowTheMoney statements/provenance: https://followthemoney.tech/docs/statements/
- GitHub deployment environments/protection: https://docs.github.com/en/actions/concepts/workflows-and-actions/deployment-environments

## 3A. Balanced product strategy — personal-first

The roadmap deliberately optimizes for a **single owner/operator** first.

The target is not feature breadth. The target is a coherent personal system in which:
- operator cognitive load stays low;
- search remains open and inspectable;
- internal complexity protects truth/recovery rather than decorating the product;
- future team mode is possible without being paid for prematurely.

Therefore:
- Web is the first universal client surface;
- PWA is justified by real mobile/network needs;
- Web + PWA are the approved client surfaces. Native Android is not part of the roadmap unless a separately approved evidence-backed exception is opened;
- team/RBAC/tenancy is deferred until a real constraint or operating requirement exists;
- external legal/operating assumptions are kept minimal and do not become an internal document-management subsystem;
- intelligence sources are added by measured contribution, not by provider count;
- every feature is evaluated by operator-time saved, decision quality improved, risk reduced, or recoverability gained.

### Product shape

The product is one system with four planes:

**Canonical Truth** → identity, business entities, orders, economics, history.

**Intelligence & Evidence** → search, resolution, claims, provenance, freshness, qualification.

**Execution & Reliability** → jobs, outbox, idempotency, reconciliation, audit, recovery, observability.

**Experience & Control** → Web/PWA, search center, dossiers, evidence, actions, system control plane.

The planes share one canonical API/domain boundary. None may create an alternate business truth.

### Complexity admission rule

A new subsystem is admitted only if it has a concrete problem, bounded scope, failure/recovery semantics, measurable value, and a removal/rollback path. Architecture is not expanded merely because a mature product elsewhere has a corresponding subsystem.

## 3. Non-negotiable development rules

### 3.1 Frozen core
Do not reopen v1.4/v1.5 core semantics for convenience.

### 3.2 One active capability boundary
Only one substantial product capability is actively implemented at a time. Documentation, tests and verification can support it; unrelated feature work does not run in parallel.

### 3.3 Vertical slice first
Prefer a thin end-to-end path over building a large isolated subsystem.

### 3.4 Evidence before automation
Do not automate a weak manual process. First establish the correct information/result manually, then encode and automate it.

### 3.5 External quality before external volume
Improve identity, provenance, freshness, contradiction handling and operator usefulness before adding many providers or large-scale crawling.

### 3.6 Every stage closes completely
A stage is not complete when code exists. It is complete only after:
- contract;
- implementation;
- negative/failure cases;
- integration;
- E2E where relevant;
- security;
- recovery/rollback where relevant;
- observability;
- CI;
- development-state update.

### 3.7 No unmeasured scale claims
Scale is increased only after real measurements justify the next constraint or architectural change.

## 4. Phase 0 — Restore and close the current boundary

### Objective
Close P46 cleanly before starting new implementation.

### Work
- fix the P46 Ruff I001 import-order failure;
- rerun the full CI matrix;
- record the CI-verified P46 commit;
- preserve MAX readiness as blocked until authoritative provider evidence changes;
- verify that manifest, development state, P46 contract and branch state agree.

### Exit criteria
- full P46 CI green — **satisfied by CI #1265 (`36283673042`) on verified commit `b4c404404b7d0cf9317caf765723a3bc2003cd46`**;
- no production code change — **verified**;
- no live MAX traffic — **verified**;
- frozen core unchanged — **verified**;
- state ledger synchronized — **completed in the P46 closure synchronization**.

### Phase 0 result
**CLOSED / VERIFIED.** P46 is complete as an evidence-revalidation boundary. MAX readiness remains blocked until authoritative provider-side idempotency and provider-side reconciliation evidence becomes available. No implementation workaround, fallback provider or kernel change is permitted.

**Next selected boundary:** Phase 2 — Mature Search and Research. Phase 1-A and Phase 1-B are CLOSED / VERIFIED.

## 5. Phase 1 — Intelligence Quality Foundation

### Objective
Build the smallest but highest-quality external intelligence engine, starting with a real operator-visible vertical slice rather than a backend-only intelligence subsystem.

### First vertical slice
Manual counterparty check:

INN/OGRN/OGRNIP → authoritative source lookup → identity resolution → evidence → contradiction/freshness → compact operator brief.

### Phase 1-A — Manual authoritative counterparty evidence check
- **Status:** CLOSED / VERIFIED by CI #1297 (`36284386157`).
- Entry point: an operator supplies an observation obtained from an authoritative FNS source.
- The bounded application capability validates INN/OGRN/OGRNIP structure and official source provenance, resolves existing identity data by tax identifier when available, persists Evidence with freshness/provenance/confidence, quarantines contradictions and emits an append-only audit record.
- Canonical API adapter exposes the same result and compact operator brief without introducing a second system of record.
- No automatic FNS network lookup, provider SDK, new database table, kernel semantic change or MAX activation is part of this substage.

### Required capabilities
- source registry;
- search plan/version;
- search relevance benchmark;
- candidate discovery;
- deterministic identifier handling;
- identity resolution;
- possible-same/manual-review state;
- statement/claim provenance;
- source reliability;
- claim confidence;
- freshness and expiry;
- contradiction handling;
- evidence classification;
- lawful-access boundary.

### Phase 1-B — Intelligence benchmark and source registry
- **Status:** CLOSED / VERIFIED by CI #1307 (`36302695693`).
- Establish the permanent benchmark corpus and source registry before adding broader automated source orchestration.
- Preserve the existing separation of candidate discovery, identity resolution, evidence provenance, source reliability, claim confidence and freshness.
- No source volume expansion, ranking gate or automatic qualification is admitted until benchmark ground truth and operator-correction metrics exist.
- Exit evidence: ten permanent synthetic cases, bounded precision/recall/FPR/FNR evaluator, provenance/freshness/operator-correction metrics, registry policy with network automation disabled, full seven-job CI gate green.

### Intelligence benchmark
Create a permanent test corpus with:
- known exact matches;
- same-name different entities;
- old identifiers;
- changed registrations;
- duplicate sources;
- contradictory addresses/statuses;
- stale claims;
- missing identifiers;
- intentionally misleading near-matches.

Measure:
- precision;
- recall where ground truth exists;
- false-positive rate;
- false-negative rate;
- provenance completeness;
- freshness correctness;
- operator correction rate.

### Exit criteria
A deterministic research result can be explained claim-by-claim:
who, what, source, date, confidence, contradiction and reason for final state.

The first operator slice can search/check a counterparty, inspect the compact result, expand evidence, and see when the result is incomplete because a source was not searched, unavailable or budget-limited.

## 6. Phase 2 — Mature Search and Research

### Status synchronization — 2026-09-27
- Phase 2-A — Search Run Integrity Boundary: **CLOSED / VERIFIED** by CI #1316 (`36304414654`) on `af813ff79802aa358eafcb68586d3bf0b105aa7d`.
- Phase 2-B — Source-Registry-Backed Search Planning: **CLOSED / VERIFIED** by CI #1324 (`36308069460`) on `ee549cada95a0a90a7647b2b01eec51fa0bdd9bc`.
- Phase 2-C — Registry-Backed Operator Search Composition: **CLOSED / VERIFIED** by CI #1330 (`36308647549`) on `16c08111e025bd267787eaa5de36c4dd53f70609`.
- Phase 2-D — Generic Runtime Composition: **CLOSED / VERIFIED** by CI #1336 (`36309294705`) on `7637871b3cac379fdff056aed90ddc73aacf760f`.
- Phase 2-E — Search Adapter Compliance Boundary: **CLOSED / VERIFIED** by CI #1340 (`36310957082`) on `abca1b26e32498105b4ea855474aab387091218c`.
- Phase 2-F — First Approved Source Adapter Readiness: **CLOSED / VERIFIED** by CI #1343 (`36311263929`) on `9e49e79c3825703117ad6b587e9cee5160feaca9`.
- Next active sub-boundary: **Phase 2-G — First Source Selection and Evidence Capture**; provider activation remains disabled.

### Objective
Scale from deterministic checks to repeatable customer discovery and deep intelligence.

### Phase 2-A — Search Run Integrity Boundary
- **Status:** CLOSED / VERIFIED by CI #1316 (`36304414654`).
- Bounded application orchestration accepts operator criteria and an ordered set of source adapters, enforces source/candidate budgets, records explicit source/run completeness, delegates candidate normalization to the existing canonical search contract and exposes benchmark metrics for precision, recall and source coverage.
- No persistence authority, external network activation, ranking score, automatic qualification or kernel change was introduced.

### Phase 2-B — Source-registry-backed search planning
- **Status:** CLOSED / VERIFIED by CI #1324 (`36308069460`).
- Binds the Phase 1-B machine-readable source registry to search planning without activating network execution.
- Validates source references, source classes, reliability metadata and lawful-access policy before a source can enter a plan.
- Keeps source reliability separate from candidate relevance and claim confidence and preserves explicit source order without ranking.
- No provider execution, new persistence authority or kernel semantic change is introduced.

### Phase 2-C — Registry-backed operator search composition
- **Status:** CLOSED / VERIFIED by CI #1330 (`36308647549`).
- Composes the verified Phase 2-A runner and Phase 2-B registry planner behind the existing canonical `/v1/search` application edge.
- Adds bounded source IDs/budgets, explicit completeness, plan version and source provenance to the search response while retaining backwards compatibility for requests that omit the new fields.
- Uses injected non-network adapters only; it does not activate provider traffic, ranking authority or automatic qualification.
- This boundary deliberately stops short of wiring the search capability into the provider-specific runtime composition.

### Phase 2-D — Generic runtime composition
- **Status:** CLOSED / VERIFIED by CI #1336 (`36309294705`).
- The verified search application capability is wired into the existing generic runtime composition through provider-neutral injection.
- A real runtime HTTP smoke path proves `/v1/search` works through the composition boundary while the existing AI/provider activation lifecycle remains unchanged.
- No provider-specific runtime semantics or network activation were introduced.

### Phase 2-E — Search Adapter Compliance Boundary
- **Status:** CLOSED / VERIFIED by CI #1340 (`36310957082`).
- The boundary validates stable source identity, source class/reliability/access metadata, lawful-access confirmation, explicit network-disabled state and callable adapter behavior before a source can be bound to canonical SearchSource.
- No provider traffic, persistence authority, ranking or qualification semantics were introduced.

### Phase 2-F — First Approved Source Adapter Readiness
- **Status:** CLOSED / VERIFIED by CI #1343 (`36311263929`).
- The provider-neutral readiness gate distinguishes absent provider selection, missing evidence, controlled-activation readiness and blocked activation.
- No provider was selected, no live network execution occurred, and no automatic activation/retry/fallback semantics were introduced.

### Phase 2-G — First Source Selection and Evidence Capture
- **Status:** IN PROGRESS / source-selection and evidence sub-boundary CLOSED / VERIFIED; activation BLOCKED.
- Selected exactly one registry-declared source: `fns_transparent_business` / FNS Transparent Business.
- Captured the source-specific adapter contract, authoritative evidence record and deterministic fixture tests.
- Verified the official FNS public-service and open-data context, including lawful-use/source-attribution conditions.
- Explicitly preserved the distinction between public/open-data reuse rights and a provider-specific automation contract.
- Remaining automation evidence gaps: provider-side rate limits, timeout semantics and machine-error contract are not authoritatively established for an automated Transparent Business path.
- Full CI #1348 (`36312176697`) passed all seven release-gate jobs on `3625d0e30309b64ebfb6eada4a2a75a4b619fa52`.
- Live provider traffic remains disabled; no automatic retry/fallback, production activation, new persistence authority, ranking authority, automatic qualification or frozen-kernel change is permitted.
- **Sub-boundary exit evidence:** source selection + evidence record + source-specific adapter contract + deterministic fixtures are verified before any activation decision.
- **Next boundary:** Phase 2-H — controlled provider execution with DaData as the parallel alternative; FNS remains a separately gated evidence hold.

### Phase 2-H — Controlled Provider Execution Boundary (DaData parallel alternative)
- **Status:** CLOSED / VERIFIED — provider lookup → Evidence runtime vertical slice and Runtime Negative Provider Outcomes & Recovery are both verified; live activation remains OFF.
- **Purpose:** introduce the first provider-specific execution path without weakening the provider-neutral search contracts or frozen kernel.
- **Primary alternative:** `dadata_organization_api` using the documented DaData organization-by-INN/OGRN API.
- **Parallel hold:** `fns_transparent_business` remains independently governed and BLOCKED for automation.
- **Classification:** `trusted_structured_dataset` / `trusted_secondary`; DaData is a provider/service aggregation layer, not the canonical authoritative source.
- **Required provider facts:** endpoint/authentication, query/count constraints, daily quota, 30 requests/second and 60 new connections/minute, HTTP 400/401/403/405/413/429/5xx mapping, application timeout policy, bounded retry classification, provenance, correlation, kill-switch, credential isolation and rollback.
- **Execution semantics correction:** DaData `find-party` is a deterministic identifier lookup/enrichment capability, not a generic region/industry discovery provider. It therefore enters through a provider-neutral `CounterpartyLookupProvider` boundary and then feeds the existing Identity/Evidence pipeline.
- **Required evidence discipline:** only documented provider semantics may be encoded as facts; unknown provider behavior remains explicitly unknown.
- **Safety:** read-only lookup permits retries from an external-effect perspective, but not unbounded retries or quota amplification. Retry/backoff/jitter and application budgets must be bounded and observable.
- **Activation:** no CI live traffic, no credentials in source control, no automatic activation and no implicit fallback to FNS or another provider. Live execution is a separate authorized operation after the complete gate.
- **Verified implementation evidence:** source registry entry; provider contract; authoritative evidence record; provider-neutral lookup port; DaData adapter; deterministic positive/negative/rate-limit/timeout/size fixtures; bounded retry tests; secret-boundary tests; activation contract; conservative secondary-evidence intake; lookup→retry→evidence composition; full seven-job release-gate CI #1377 (`36315266092`) GREEN; final synchronized composition/docs gate CI #1383 (`36315401510`) GREEN; controlled activation operation and API control-plane CI #1392 (`36316219807`) GREEN.
- **Controlled activation operation:** provider-specific gate, dedicated RBAC permissions, explicit operator confirmation, disabled-by-default configuration, redacted activation/rollback telemetry, fail-closed kill-switch, rollback without schema changes, and dedicated authenticated API endpoints are implemented as a separate control-plane boundary. The provider identifier is taken from the route path to avoid duplicate identity input.
- **Exit evidence:** dedicated RBAC permissions, explicit operator confirmation, route-path provider identity, readiness fail-closed gate, disabled-by-default configuration, redacted activation/rollback telemetry, kill-switch rollback, authenticated API endpoints and full CI #1392 (`36316219807`).
- **Runtime rehearsal evidence:** explicit CounterpartyProviderRuntimeAssembly, injected readiness witness, disabled-by-default activation state, deterministic fake-provider boundary, authenticated activation/rollback HTTP path, readiness fail-closed behavior and no real network on assembly/startup; full seven-job CI #1397 (`36316599417`) GREEN.
- **Runtime vertical-slice evidence:** dedicated lookup permission, path-bound provider identity, lazy activated binding, existing retry/evidence composition reused without duplication, explicit confidence/expiry, UnitOfWork-backed Evidence intake, correlation-preserving audit, canonical Identity non-promotion and rollback fail-closed behavior; full seven-job CI #1402 (`36317002134`) GREEN.
- **Runtime Negative Provider Outcomes & Recovery:** CLOSED / VERIFIED by full CI #1404 (`36317178100`) on `758690225996c1c2cca95cbbd3b1c56638d69db8`.
- Deterministic runtime evidence covers not-found, bounded rate-limit retry/exhaustion, provider 5xx, transport recovery, contradiction quarantine, no-fallback behavior and terminal-error no-partial-state guarantees.
- Exit condition satisfied: complete seven-job release gate GREEN; no live DaData traffic; no credentials in source control; no DB schema or frozen-kernel change.
- **No changes to:** v1.4 semantics, DB schema, canonical identity semantics or frozen kernel.

### Work
- Phase 2-H provider-specific execution for DaData behind the provider-neutral CounterpartyLookup boundary; the controlled execution boundary is now CLOSED.
- multi-source search orchestration;
- search/source budgets;
- direct operator search without mandatory ranking gates;
- reversible/explainable ranking;
- explicit search completeness state;
- R1/R2/R3/R4 modes;
- selective deep research triggers;
- source waterfall;
- graph/relationship pivots for deep cases;
- reputation/risk boundary;
- monitoring and revalidation;
- search-quality metrics.

### Principle
Discovery optimizes recall.
Resolution optimizes identity precision.
Research optimizes decision evidence.

Do not collapse these three tasks into one score.

### Exit criteria
A search run produces a reproducible, evidence-backed candidate set and a compact intelligence brief without flooding the operator with raw source noise.

## 7. Phase 3 — Contact Preparation

### Objective
Convert intelligence into a high-quality first-contact package.

### Work
For each qualified candidate:
- likely decision-maker/role hypothesis;
- evidence-backed reason for contact;
- value hypothesis;
- opening;
- qualifying questions;
- objection branches;
- next-step objective;
- explicit forbidden claims;
- dossier/evidence snapshot.

### Quality benchmark
Build a contact-script test set covering:
- correct LPR;
- uncertain LPR;
- gatekeeper;
- wrong person;
- strong interest;
- no current need;
- price-first response;
- request for documents;
- request for credentials;
- contradictory dossier.

### Exit criteria
The operator can open a verified client dossier and receive a usable, evidence-grounded first-contact script without manually reconstructing the research.

## 7A. Phase 3A — Repeat Orders & Business Continuity (temporary Shema live mode)

### Objective
Until Bitrix24 becomes the live business plane, Shema must provide a usable repeat-order workflow using the already frozen Order/Economics semantics, without reopening the kernel.

### Operator workflow
- **Повторный заказ** is a first-class action from a completed/eligible prior order.
- The operator sees the prior order context, recurrence pattern, current evidence freshness, current pricing assumptions and capacity/date assumptions.
- A repeat order is created as a new immutable order transaction; the previous order is never edited.
- The operator can pause, skip once, resume or cancel the recurrence plan.
- Current counterparty status and required evidence are revalidated before confirmation.
- All repeat-order mutations are idempotent and audited.

### Temporary authority
Before Bitrix24 handoff:
- Shema owns the live repeat order and the limited transaction-scoped economics required to execute it;
- the frozen Order/Economics kernel semantics are reused rather than changed;
- no accounting, tax, payroll or full finance subsystem is introduced.

### Bitrix24 transition
The complete cutover is governed by:
`architecture/repeat_order_transition_contract.json`.

A migrated transaction is not purged from Shema merely because Bitrix24 accepted the first write. Purge is permitted only after:
**snapshot → Bitrix acknowledgement → full readback → completeness proof → recovery snapshot verification**.

After successful migration:
- live Order/Economics operational rows are purged;
- a minimal frozen lineage tombstone remains;
- Order/Economics tabs disappear from the Shema operator interface without a broken layout;
- deep links show an explicit “moved to Bitrix24” state;
- Bitrix24 becomes the only live transaction authority.

### Exit criteria
The operator can create and manage repeat orders in Shema safely before Bitrix24, and a verified migration can move the complete business transaction/history package to Bitrix24 without duplicate authority or UI breakage.

## 7B. Phase 3B — Public Intake Data Plane, Trust Boundary and Counterparty Preflight

### Objective
Accept real B2B client demand through the public site while isolating raw submissions from the canonical Shema database and preserving durable notifications.

### Core design
- raw client form data is written to a **dedicated PostgreSQL database** through the canonical API;
- the intake database has separate credentials, bounded access and independent recovery tests;
- request persistence and the intake outbox are atomic;
- Shema receives only the accepted business context required for operator work;
- the operator notification center is projected from the durable intake outbox;
- notification floods are aggregated, while critical alerts are durable and retryable;
- counterparty preflight remains deterministic and GPT-free for registry truth.

### Exit criteria
A request survives Shema outages after accepted intake, produces exactly-once operator-visible notification semantics under retries, and can be reconstructed from intake record → preflight snapshot → Shema request context → outcome.

### Implementation synchronization — 2026-09-29
**Phase 3B is CLOSED / VERIFIED.** Full seven-job release-gate CI #2004 (`36558811275`) on exact E2E HEAD `254f7467e05fd92d0c594558f6a4263684040557` proves the complete accepted-intake → Shema outage → durable outbox → replay → canonical request context → operator notification → duplicate-safe replay path. Migration `0014_public_intake_projection.sql` is recovered by the PITR drill. The next implementation boundary is **Phase 3C — Counterparty Verification, Monitoring & Favorites**.

## 7C. Phase 3C — Counterparty Verification, Monitoring & Favorites

### Objective
Turn the existing lead-search field into a dual-purpose operator tool without creating a second search engine.

### Operator mechanism
When the operator enters an exact INN/OGRN/OGRNIP:
- the search mode automatically becomes **Проверка контрагента**;
- the operator gets deterministic identity/status verification immediately;
- **Глубокая разведка** invokes the existing bounded intelligence source policy only after identity resolution;
- **Сохранить в мониторинг** creates a daily change-monitoring record;
- **В избранное** creates a personal shortcut.

The separate **Контрагенты** workspace contains:
**Проверка | Мониторинг | Избранные**.

Monitoring is organizationally distinct from favorites:
- monitoring produces change events and notifications;
- favorites do not schedule external lookups;
- monitoring entries are updated from official/verified registry snapshots;
- registry outage never creates a false “changed” event.

### Exit criteria
A monitored counterparty has reproducible snapshots, deterministic change detection, severity-aware notifications, checkpointed batch recovery and a direct link back to its dossier/history.

### Implementation synchronization — 2026-09-29
**Phase 3C-1 — Counterparty Monitoring & Favorites runtime model/persistence is CLOSED / VERIFIED** by full seven-job release-gate CI #2041 (`36561799870`). The verified slice includes actor-scoped monitoring, personal favorites, deterministic identifier validation, snapshot hashing/provenance, change detection, audit/outbox, protected API routes and explicit runtime composition.

**Phase 3C-2 — Checkpointed Daily Counterparty Monitoring Worker + Provider-Outage/Recovery Semantics is CLOSED / VERIFIED** by full seven-job release-gate CI #2073 (`36577339818`) on the exact implementation HEAD after the final adversarial additions. The verified slice includes durable daily batch checkpoints, bounded parallelism, lease ownership/reclaim CAS semantics, deterministic retry/backoff limits, provider-outage handling without false changes, replay-safe observation idempotency, max-attempt fail-closed behavior and stale-worker negative coverage.

**Phase 3C — Counterparty Verification, Monitoring & Favorites is now CLOSED / VERIFIED.** The complete contract boundary is satisfied without changing frozen kernel semantics. The next implementation boundary is **Phase 4 — Web Operator System**.

## 8. Phase 4 — Web Operator System

### Phase 4-4E — CLOSED / VERIFIED
System/control-plane hardening and the final cross-surface acceptance contract are closed. Runtime HEAD `13de9b974bf59070dfbe2f4cd69f5ec7255c42f4` passed full seven-job CI run `36588002294` — **7/7 GREEN**. Phase 4 therefore closes as **Web Operator System — CLOSED / VERIFIED**. The subsequent synchronization commit changes documentation/security contract only.

### Phase 4-4D — CLOSED / VERIFIED
Repeat Orders & Business Continuity are exposed through the canonical Web/API boundary with idempotency, ownership and policy delegated to the existing RepeatOrderService. Capability remains fail-closed until a real server-side revalidator is composed. CI: `36584780497`. Next: **Phase 4-4E — System/control-plane hardening and global acceptance**.

### Phase 4-4B — CLOSED / VERIFIED
Public service/landing + advanced intake, source/UTM attribution, referrer/entry surface, correlation presentation and the same Web projection for MAX are verified on CI run `36582610189`. Next active element: **Phase 4-4C — Operator causal workbench**.

### Phase 4-4A — CLOSED / VERIFIED
The first Web Operator boundary is verified on CI run `36581745238`: same-origin Web shell/assets, protected operator API boundary, public intake shell, MAX static projection, capability-aware navigation and client-side no-persistence safeguards. The next active boundary is **Phase 4-4B — Public Client Intake + Attribution + MAX projection hardening**.

### Objective
Create the primary human operating surface over proven B2B workflows and consolidate the vertical slices into one coherent operator system. This is not the first appearance of UI; earlier phases already include minimal operator surfaces for validation.

### Work

Build the public and operator surfaces from the same canonical API:
- public company site;
- advanced client request form;
- source/UTM attribution and request correlation;
- protected operator workspace;
- client request intake queue;
- client dossier;
- intelligence/evidence view;
- qualification;
- contact preparation;
- Repeat Orders & Business Continuity;
- action;
- result;
- system control plane;
- MAX mini-app projection of the same public request surface;
- canonical operator-interface contract: `architecture/operator_interface_contract.json`;

### Public-client domain
- canonical public domain: `схемагрупп.рф`;
- public request intake never creates authoritative live transaction state;
- source attribution is preserved from advertising/direct entry through request, operator handling and eventual business handoff;
- the same public web application is used by the MAX mini-app through a static HTTPS URL;
- inSales is detached only after the new site, HTTPS, redirects and health checks are validated; existing DNS and mail records are preserved during cutover.

### Rules
- canonical API only;
- no client-owned business truth;
- one design system;
- compact default view;
- technical detail one level deeper;
- responsive;
- keyboard-friendly;
- accessibility baseline;
- E2E critical flows;
- visual regression for critical screens.

### Exit criteria
The complete public-client + operator path works in one Web surface without bypassing server contracts, while direct search, evidence drill-down, technical diagnostics and safe operator overrides remain available without forcing the operator through a hidden ranking/qualification pipeline.

## 9. Phase 5 — PWA — CLOSED / VERIFIED

### Objective
Provide installable mobile-capable access without creating a second system.

### Work
- installability;
- service-worker/update lifecycle;
- safe offline read cache;
- explicit offline/pending states;
- reconnect;
- bounded mutation queue only where idempotency is proven;
- synchronization conflict handling;
- safe updates and rollback.

### Exit criteria
Temporary network loss does not corrupt canonical state or create duplicate effects.

### Closure evidence — 2026-09-30
Phase 5 is **CLOSED / VERIFIED** on final implementation HEAD `337b3c3f8465b406d13f6655f8e65910efe4524a` by full seven-job release gate `36635383440` — **7/7 GREEN**. Acceptance contract: `tests/test_phase5_pwa_acceptance.py`. Security invariant: SI-26. A global adversarial review found and required closure of one public-bootstrap trust-boundary defect (PWA worker/manifest routes were not in the unauthenticated allowlist); the allowlist and HTTP-level regression test were added, then the complete gate passed. No P0/P1 findings remain open. No frozen-kernel semantics or second business authority were introduced.

**Next approved boundary:** Phase 6 — Production Web/PWA Consolidation.

## 10. Phase 6 — Production Web/PWA Consolidation — CLOSED / VERIFIED

### Objective
Finish the primary operator experience on Web and PWA. Android is explicitly removed from the approved roadmap.

### Rules
- Web and PWA use the same canonical API/domain semantics;
- no additional native client business layer is created;
- mobile-specific requirements must be proven within PWA before another surface is considered;
- offline/read-cache and idempotent pending mutations remain bounded and server-authoritative.

### Exit criteria
Web and PWA provide the complete proven operator workflow without a second business-rule implementation.

### Closure evidence — 2026-09-30
Phase 6 is **CLOSED / VERIFIED** on final implementation HEAD `1b75bfb46f73309597420b4e1b7762c1477a1e8c` by full seven-job release gate `36637312890` — **7/7 GREEN**. Acceptance: `tests/test_phase6_operator_consolidation_acceptance.py`. Global adversarial review covered the frozen kernel, post-core contracts, runtime, persistence, integrations, operator workflow, security/recovery and migration boundaries. Two trust-boundary findings were required to be fixed before closure: operator navigation now fails closed after capability rejection, and the handoff workspace cannot imply that an external Bitrix transfer was acknowledged when no integration provider is composed. Both are covered by acceptance tests. No frozen-kernel change, second business authority, or external success simulation was introduced.

**Next approved boundary:** deployment target selection remains deferred until a measured need and an executable, current, cost-validated path are established.

### Closure evidence — 2026-09-30
Phase 6 is **CLOSED / VERIFIED** on final HEAD `1b75bfb46f73309597420b4e1b7762c1477a1e8c` by full seven-job release gate `36637312890` — **7/7 GREEN**. The final adversarial review fixed capability-rejection fail-closed behavior and removed any handoff UI implication of external ACK when no integration provider is composed. SI-27 remains enforced; frozen kernel unchanged.

**Next approved boundary:** deployment target selection remains deferred until a measured need and an executable, current, cost-validated path are established.

## 10A. Operator Interface & Multi-Operator Doctrine

### Interface principles
The operator interface is an operational safety mechanism, not decoration. The authoritative implementation blueprint is `architecture/operator_interface_contract.json`, aligned to mature Bitrix24 CRM patterns. The adopted pattern is:
- compact summary/highlights at the top;
- Details, Related records and Activity/History as predictable information groups;
- list views as work queues with saved filters/sorts and quick actions;
- quick/contextual views for inspection without losing the current work context;
- process stages/checklists as guidance, while server-side contracts remain authoritative;
- progressive disclosure: evidence and technical diagnostics one level deeper;
- personal view preferences without changing canonical business logic;
- keyboard-friendly desktop, responsive Web, touch-friendly PWA, accessibility baseline;
- clear loading/empty/degraded/error/offline/pending states;
- destructive/irreversible actions require deliberate confirmation.

### Multi-operator foundation
From the beginning the system supports growth from one operator to several without duplicating business truth:
- explicit actor identity on actions;
- owner/assignee/team queue separated from customer identity;
- audited assignment/reassignment and handoff;
- revision/concurrency protection so stale writes fail rather than overwrite newer work;
- role/permission enforcement on the server;
- shared records without shadow copies;
- explicit conflict outcomes: reload, accept current, merge supported fields, or manual review;
- durable work state instead of chat/private UI state;
- notifications derived from durable server state.

This is a bounded extension around the frozen core, not a new system-of-record or a premature multi-tenant architecture.

## 11. Deployment target selection and production readiness — DEFERRED

### Objective
Select and validate a production deployment path only when real operating constraints justify it.

### Admission criteria
- current provider documentation and limits verified from primary sources;
- minimal executable deployment path proven before adding production infrastructure;
- total cost and free/quota allowances verified for the actual intended workload;
- rollback, recovery, security and data-authority boundaries remain provider-neutral;
- no provider-specific deployment logic enters the canonical domain or frozen kernel.

### Exit criteria
A minimal production deployment can be created, observed, recovered and removed deterministically, with current evidence and without a second business authority.

## 12. Phase 8 — Production Operations

### Objective
Turn the developed system into a safely operated long-lived system.

### Work
- staging/production environments;
- protected deployment;
- secrets management;
- reproducible artifacts;
- staged rollout;
- health/readiness;
- operational dashboards;
- alert policy;
- client + server SLOs;
- real production error budgets;
- backup/restore verification in target environment;
- rollback;
- release audit trail.

### Principle
Roll out gradually, observe, and roll back first when a release is unhealthy. This follows mature SRE release practice.

### Exit criteria
A release can be deployed, observed, rolled back and reconstructed without ad hoc manual intervention.

## 13. Phase 9 — Bitrix24 Business Control Plane Integration & Transaction Cutover

### Objective
Turn Bitrix24 into the mature live business plane and safely retire the temporary Shema live Order/Economics mode after verified migration.

### Business-plane composition
The Setup Agent configures only capabilities actually available on the portal:
- CRM: companies, contacts, deals, pipelines and permissions;
- repeat/recurring sales;
- Smart Process Automation for bounded logistics/routing/executor workflows;
- tasks, assignments and team processes;
- inventory/product catalog and product-level economics where supported;
- CRM documents and signing where supported;
- tender connector / approved Bitrix24 Market integration for tender work where a native capability is unavailable;
- external accounting/finance integration where authoritative accounting is required.

Bitrix24 documentation confirms that CRM supports repeat sales, recurring deals, Smart Process Automation, inventory management, CRM documents and role-based permissions; exact availability remains plan-dependent. urlBitrix24 repeat saleshttps://helpdesk.bitrix24.com/open/24147842/ urlBitrix24 recurring dealshttps://helpdesk.bitrix24.com/open/17240254/ urlBitrix24 Smart Process Automationhttps://helpdesk.bitrix24.com/open/19141012/ urlBitrix24 inventory managementhttps://helpdesk.bitrix24.com/open/26000719/ urlBitrix24 CRM documentshttps://helpdesk.bitrix24.com/open/19441484/

### Full transaction/history migration
For each selected customer transaction:
1. freeze the Shema live transaction;
2. build the complete migration package;
3. reserve/create the Bitrix24 business object;
4. transfer all required Order/Economics fields and relevant customer/business history;
5. read back the complete result;
6. verify counts, references, monetary aggregates and payload hash;
7. only then mark the Shema data PURGE_ELIGIBLE;
8. purge live operational Order/Economics rows;
9. retain the minimal frozen lineage tombstone;
10. hide the obsolete Shema UI capability.

A lost or ambiguous Bitrix response always enters reconciliation before another write. A failed readback never permits purge.

### Non-goals
- no wholesale Shema database migration;
- no parallel live Order/Economics authority after acknowledged cutover;
- no tender/document subsystem inside Shema;
- no blind assumption that a Bitrix24 plan exposes every desired capability.

### Exit criteria
Bitrix24 (plus explicitly selected specialist integrations) can operate the live business lifecycle, while Shema retains intelligence, evidence, learning context and only the minimum immutable lineage required for causal continuity.

## 14. Phase 10 — External Provider Activation and MAX

### Objective
Activate external effects only after their safety contracts are proven.

### Work
- complete provider-specific evidence;
- provider capability contracts;
- real adapter tests;
- ambiguous-outcome behavior;
- live test environment;
- bounded production activation;
- monitoring;
- rollback.

### MAX rule
MAX stays blocked until provider-side idempotency or deterministic reconciliation is actually evidenced.

No workaround provider or implicit fallback is introduced merely to bypass the blocker.

### Exit criteria
A real external effect is safe under timeout, lost-response, retry, duplicate and recovery scenarios.

## 15. Phase 11 — Learning Loop

### Objective
Close the loop from outcomes back into intelligence and operator decisions without importing the complete CRM/finance database into Shema.

### Inputs
- accepted/rejected candidates;
- reason for rejection;
- contactability;
- script outcomes;
- next-step outcomes;
- won/lost or completed outcome classes from Bitrix24;
- repeat-business signals;
- provider/source quality;
- operator corrections;
- freshness failures;
- optional coarse economic outcome features only when explicitly justified.

### Outputs
- better search plans;
- better source selection;
- better research depth selection;
- better qualification;
- better contact preparation;
- better source/provider selection;
- measured infrastructure/resource policy.

### Rule
Learning changes controlled application policy, not canonical historical truth.

## 16. Phase 12 — Measured scalability and team mode

### Objective
Scale only where actual use creates a measured constraint.

### Work only when justified
- worker scaling;
- caching;
- queue partitioning;
- read replicas;
- search indexing;
- service extraction;
- multi-user/RBAC expansion;
- tenancy.

### Trigger
A real bottleneck or isolation/security requirement must exist before introducing structural complexity.

## 16A. Operator freedom and complexity guardrails

These are permanent roadmap rules, not optional UX preferences:

- ranking prioritizes but does not silently erase eligible candidates;
- every material exclusion has an inspectable reason;
- `NOT_SEARCHED` is never presented as `NOT_FOUND`;
- source-unavailable and budget-limited research remain visible;
- no universal opaque score substitutes for evidence;
- UI complexity must not increase unless operator value is demonstrated;
- mature-system patterns are adopted by principle, not copied wholesale by subsystem count.

## 17. What must NOT happen

- no v1.6/v1.7 kernel expansion for UI convenience;
- no parallel client business-rule implementations;
- - no giant intelligence graph before useful bounded workflows exist;
- no mass source integration before both identity and search-relevance benchmarks exist;
- no mandatory qualification/ranking gate that prevents direct operator search;
- no enterprise/team-mode complexity before an actual operating constraint exists;
- no AI truth authority;
- no provider activation because an API endpoint exists;
- no automatic retries without external-effect safety evidence;
- no second system of record in clients;
- no microservices merely as a maturity signal;
- no scale claims without measurements;
- no release without full gate evidence.

## 18. Priority order

The practical priority is:

0. P46 closure
1. Intelligence quality benchmark + manual counterparty verification
2. Search/Research maturity
3. Contact preparation
4. Repeat Orders & Business Continuity (temporary Shema live mode)
5. Public Intake Data Plane + Trust Boundary + Counterparty Preflight
6. Counterparty Verification, Monitoring & Favorites
7. Web/PWA public client surface + operator workspace + MAX mini-app projection
8. Deployment target selection and production readiness
9. Bitrix24 business-plane configuration + full transaction/history cutover
10. Production operations and guarded external activation / MAX
11. Learning loop
12. Measured scalability/team mode

Where two capabilities are tightly coupled, build them as one vertical slice rather than separate half-finished layers.

## 19. Final target state

The mature Shema system should allow the owner to move through one coherent loop:

**Find → Resolve → Verify → Understand → Qualify → Prepare contact → Handoff → Act → Observe result → Learn**

while the platform guarantees:

**canonical truth → evidence → safe execution → audit → recovery → explainability → controlled evolution**

The product should feel like one durable personal instrument, not a collection of enterprise subsystems:
- direct search remains possible;
- evidence is one level deeper;
- technical controls are available but not imposed;
- uncertainty is explicit;
- external actions are guarded;
- history remains reconstructable;
- new capability is added only when it earns its complexity.

The system should remain simple for the operator even as its internal reliability and intelligence mechanisms become sophisticated.

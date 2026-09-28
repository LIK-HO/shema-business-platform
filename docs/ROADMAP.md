# Shema Business Platform — Development Roadmap

## 1. Purpose

This roadmap defines the optimal post-core development strategy for Shema as a personal, scalable, reliable and durable system.

It is not a SaaS breadth roadmap.

The frozen v1.4 kernel and certified v1.5 Core Maturity remain the protected internal foundation. New capability is built outside the kernel through bounded vertical slices.

The governing product loop is:

SEARCH → INTELLIGENCE → EVIDENCE → QUALIFICATION → CONTACT PREPARATION → DOCUMENT PACK → ACTION → RESULT → LEARNING

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
- Android is justified only where native capabilities provide material value;
- team/RBAC/tenancy is deferred until a real constraint or operating requirement exists;
- legal/configuration coverage grows from real transaction patterns rather than attempting to model the whole legal universe;
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

## 6A. Phase 2-I — Procurement Foundation (Dormant / B2G Deferred)

### Status
**CLOSED / VERIFIED as a technical foundation; product activation and further Shema development are DEFERRED.**

### Strategy correction
B2B is the first operating stage. The system must first prove repeatable B2B acquisition, qualification, contact, service delivery and unit economics in real work.

The existing procurement foundation is retained only because it is already a verified provider-neutral boundary. It is **not** a reason to pull B2G/tender complexity into the early product.

### Rules
- no new procurement runtime is developed in Shema before the Bitrix24 business-plane stage;
- no tender workspace is added to the early Shema operator interface;
- no tender submission/participation automation is built in Shema;
- no HTML scraping fallback;
- existing provider-neutral contracts and deterministic fixtures remain reusable technical assets;
- B2G/tender execution is evaluated later inside Bitrix24 or a mature tender capability integrated with the business plane;
- Shema remains focused on intelligence, evidence, qualification, preparation and handoff.

### Exit
This foundation is considered closed as dormant infrastructure. No further Phase 2-I sub-work is implicitly opened.

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

## 7A. Phase 3A — Repeat Business Preparation

### Placement
This capability sits between Contact Preparation and Document Configuration. Its purpose is to detect and prepare repeat demand, not to create a second transaction engine.

### Objective
Turn repeat business into a first-class operator workflow while leaving live deal/order, pricing and economic authority to the mature business plane.

### Chosen pattern
Use a reusable **Repeat Business Rule / Customer Pattern** attached to the canonical customer. The rule stores recurrence signals, preparation window, last known business reference, and references to relevant evidence/document configuration. Each recurrence creates a **fresh preparation/handoff snapshot**. It never becomes the live order ledger.

### Operator workflow
- show **Upcoming repeat business** in the work queue;
- one compact rule exposes recurrence pattern, next preparation window, last known business reference and evidence freshness;
- primary actions: **Prepare next handoff**, **Skip once**, **Pause**, **Resume**, **Change pattern**;
- revalidate evidence, current commercial assumptions and document requirements before preparing the handoff;
- prevent duplicate open preparation snapshots for the same recurrence window;
- preserve lineage from the preparation snapshot to the originating customer and prior outcome;
- after Bitrix24 handoff becomes available, map the preparation snapshot to a Bitrix recurring/repeat-deal capability rather than reimplementing that engine in Shema.

### Research basis
Mature CRM/ERP products treat recurrence as a reusable rule/template that generates distinct business transactions. Bitrix24, Salesforce and SAP expose this pattern in different forms. Shema adopts only the preparation/intelligence part of the pattern and delegates the live transaction engine to the business plane. citeturn496805search1turn495622search5turn496805search11

### Exit criteria
The operator can identify upcoming repeat demand, review changed evidence/configuration, and generate a traceable handoff package without creating a live transaction or calculating authoritative business economics in Shema.

## 8. Phase 4 — Document Configuration & Handoff Preparation

### Objective
Produce an evidence-backed document requirement/configuration snapshot without turning Shema into the final legal-document execution or signing system.

### Work
- legal-role matrix;
- tax/regime configuration;
- service/work type;
- payment/acceptance requirements;
- EDO/e-signature requirements;
- document applicability rules;
- complete baseline document registry: service contract, one-off service/work order, specifications/technical statements, commercial offers/quotations, invoice/payment request requirements, acceptance acts, УПД or equivalent tax documents where applicable, addenda/change orders, reconciliation, NDA/confidentiality, authority/power-of-attorney, termination and procurement/tender packs;
- template/configuration registry;
- effective dates;
- legal-source references;
- document versioning;
- generation/configuration snapshots and checksums;
- mandatory/conditional/recommended/optional/not-applicable status;
- NPD status/check controls where relevant;
- LEGAL_REVIEW_REQUIRED path.

### Ownership boundary
Shema prepares the **requirement set and configuration snapshot**. Final business document issuance, signing, storage, approval and legally operative lifecycle belong to Bitrix24 or a dedicated business/EDO system after handoff.

### Exit criteria
For each supported configuration the system can explain why a document is required or excluded and produce a versioned handoff package that a downstream business system can execute without reconstructing the intelligence context.

## 9. Phase 5 — Web Operator System

### Objective
Create the primary human operating surface over proven B2B workflows and consolidate the vertical slices into one coherent operator system. This is not the first appearance of UI; earlier phases already include minimal operator surfaces for validation.

### Work
Build only the workflows already proven in Phases 1–4:
- command/search center;
- counterparty check;
- repeat-business preparation queue;
- client dossier;
- intelligence/evidence view;
- qualification;
- contact preparation;
- document pack;
- action;
- result;
- system control plane.

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
The complete operator path works in one Web surface without bypassing server contracts, while direct search, evidence drill-down, technical diagnostics and safe operator overrides remain available without forcing the operator through a hidden ranking/qualification pipeline.

## 10. Phase 6 — PWA

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

## 11. Phase 7 — Production Web/PWA Consolidation

### Objective
Finish the primary operator experience on Web and PWA. Android is explicitly removed from the approved roadmap.

### Rules
- Web and PWA use the same canonical API/domain semantics;
- no additional native client business layer is created;
- mobile-specific requirements must be proven within PWA before another surface is considered;
- offline/read-cache and idempotent pending mutations remain bounded and server-authoritative.

### Exit criteria
Web and PWA provide the complete proven operator workflow without a second business-rule implementation.

## 11A. Operator Interface & Multi-Operator Doctrine

### Interface principles
The operator interface is an operational safety mechanism, not decoration. The adopted pattern is:
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

## 12. Phase 8A — Yandex Cloud Production Foundation

### Objective
Move the proven modular monolith into Yandex Cloud without changing domain semantics or creating a second persistence authority.

### Work
- containerized canonical API/runtime in Serverless Containers;
- API Gateway as the explicit external edge;
- Cloud Functions only for narrow scheduled/triggered work;
- Lockbox for provider/API credentials;
- Container Registry for immutable application artifacts;
- Object Storage for bounded large evidence objects and exports;
- Monium + Monitoring for observability and operational health;
- Managed PostgreSQL as the production canonical transactional database;
- target VPC/private networking for production database access;
- cost budgets and alerts.

### Free/minimal deployment rule
The serverless shell can begin inside Yandex Cloud free allowances. Real production data requires Managed PostgreSQL cost; the architecture must not replace PostgreSQL with a second database merely to avoid that cost.

### Queue rule
The existing PostgreSQL job/outbox model remains the business reliability authority. Yandex Message Queue may be introduced later as transport/fanout when measured workload requires it; it must not become a competing transaction authority.

### Exit criteria
The same frozen kernel and canonical API run in Yandex Cloud with verified secrets, database connectivity, backup/recovery, health checks, observability and rollback, without introducing duplicate business state.

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

## 13. Phase 9A — Bitrix24 Business Control Plane Integration

### Objective
Introduce Bitrix24 as the mature external business-process and transaction-control plane, without rebuilding CRM/finance/tender execution inside Shema.

### Ownership
Shema remains authoritative for:
- source observations;
- identity resolution;
- evidence/provenance/freshness;
- intelligence and qualification;
- procurement observations;
- contact preparation;
- AI run lineage;
- learning context.

Bitrix24 becomes authoritative after handoff for:
- live lead/deal/order lifecycle;
- transactional pricing;
- invoices/payments and business economics;
- live communication history;
- assignments and business process stages;
- team workflows and approvals;
- business documents configured for the portal.

### Integration phases
1. Single-portal proof with an inbound webhook.
2. Outbound event intake for selected business events.
3. Idempotent Shema outbox for handoff commands.
4. Reconciliation and field-ownership map.
5. OAuth 2.0 application boundary before multi-user/multi-portal maturity.
6. Establish operator causal continuity and multi-operator ownership after handoff.
7. Evaluate B2G/tender capability in Bitrix24 or a mature integrated tender tool.
8. Outcome-only return path for learning.

### Non-goals
- no bidirectional same-field writes;
- no full CRM mirror in Shema;
- no second finance system;
- no copying detailed personnel data without a separately approved need.

### Exit criteria
A qualified opportunity can be handed from Shema to Bitrix24 with traceable identity and evidence references, and the resulting business outcome can return to Shema without creating competing truth.

## 13. Phase 9 — External Provider Activation and MAX

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

## 14. Phase 10 — Learning Loop

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
- better document configuration;
- better source/provider selection;
- measured infrastructure/resource policy.

### Rule
Learning changes controlled application policy, not canonical historical truth.

## 15. Phase 11 — Measured scalability and team mode

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

## 15A. Operator freedom and complexity guardrails

These are permanent roadmap rules, not optional UX preferences:

- ranking prioritizes but does not silently erase eligible candidates;
- every material exclusion has an inspectable reason;
- `NOT_SEARCHED` is never presented as `NOT_FOUND`;
- source-unavailable and budget-limited research remain visible;
- no universal opaque score substitutes for evidence;
- UI complexity must not increase unless operator value is demonstrated;
- mature-system patterns are adopted by principle, not copied wholesale by subsystem count.

## 16. What must NOT happen

- no v1.6/v1.7 kernel expansion for UI convenience;
- no parallel client business-rule implementations;
- no early B2G/tender subsystem inside Shema;
- no giant intelligence graph before useful bounded workflows exist;
- no mass source integration before both identity and search-relevance benchmarks exist;
- no mandatory qualification/ranking gate that prevents direct operator search;
- no enterprise/team-mode complexity before an actual operating constraint exists;
- no AI truth authority;
- no provider activation because an API endpoint exists;
- no automatic retries without external-effect safety evidence;
- no legal template treated as universally correct;
- no second system of record in clients;
- no microservices merely as a maturity signal;
- no scale claims without measurements;
- no release without full gate evidence.

## 17. Priority order

The practical priority is:

0. P46 closure
1. Intelligence quality benchmark + manual counterparty verification
2. Search/Research maturity
3. Contact preparation
4. Document Configuration & Handoff Preparation
5. Web operator system + repeat-business workspace
6. PWA
7. Production Web/PWA consolidation
8. Yandex Cloud production foundation
9. Bitrix24 business-plane integration + multi-operator operating model
10. B2G/tender capability inside Bitrix24 or mature integrated tender tooling
11. Production operations and guarded external activation / MAX
12. Learning loop
13. Measured scalability/team mode

Where two capabilities are tightly coupled, build them as one vertical slice rather than separate half-finished layers.

## 18. Final target state

The mature Shema system should allow the owner to move through one coherent loop:

**Find → Resolve → Verify → Understand → Qualify → Prepare contact → Prepare documents → Act → Observe result → Learn**

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

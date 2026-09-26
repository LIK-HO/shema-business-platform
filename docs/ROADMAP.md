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

**Experience & Control** → Web/PWA/Android, search center, dossiers, evidence, actions, system control plane.

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
- full P46 CI green;
- no production code change;
- no live MAX traffic;
- frozen core unchanged;
- state ledger synchronized.

## 5. Phase 1 — Intelligence Quality Foundation

### Objective
Build the smallest but highest-quality external intelligence engine, starting with a real operator-visible vertical slice rather than a backend-only intelligence subsystem.

### First vertical slice
Manual counterparty check:

INN/OGRN/OGRNIP → authoritative source lookup → identity resolution → evidence → contradiction/freshness → compact operator brief.

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

### Objective
Scale from deterministic checks to repeatable customer discovery and deep intelligence.

### Work
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

## 8. Phase 4 — Legal / Document Configuration Engine

### Objective
Turn a verified client and transaction configuration into a correct selectable document pack.

### Work
- legal-role matrix;
- tax/regime configuration;
- service/work type;
- payment/acceptance configuration;
- EDO/e-signature configuration;
- document applicability rules;
- template registry;
- effective dates;
- legal-source references;
- document versioning;
- generation snapshots and checksums;
- mandatory/conditional/recommended/optional/not-applicable statuses;
- NPD status/check controls where relevant;
- LEGAL_REVIEW_REQUIRED path.

### Exit criteria
For each supported configuration the system can explain why every document is included or excluded, and reproduce the exact generated pack from its configuration/version snapshot.

## 9. Phase 5 — Web Operator System

### Objective
Create the primary human operating surface over proven workflows and consolidate the vertical slices into one coherent operator system. This is not the first appearance of UI; earlier phases already include minimal operator surfaces for validation.

### Work
Build only the workflows already proven in Phases 1–4:
- command/search center;
- counterparty check;
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

## 11. Phase 7 — Android

### Objective
Add native Android capability only where it provides material value beyond PWA.

### Native-first candidates
- notifications;
- background execution;
- secure device storage;
- camera/photo evidence;
- fast field workflows;
- network-aware operation;
- device-specific integrations.

### Rules
- same canonical API;
- same domain semantics;
- same idempotency;
- no duplicated business rules;
- local data remains cache/read model or bounded offline queue.

### Exit criteria
Web/PWA/Android remain one system with different interaction surfaces.

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
Close the loop from outcomes back into intelligence and operator decisions.

### Inputs
- accepted/rejected candidates;
- reason for rejection;
- contactability;
- script outcomes;
- next-step outcomes;
- order;
- revenue/cost/margin;
- provider/source quality;
- operator corrections;
- freshness failures.

### Outputs
- better search plans;
- better source selection;
- better research depth selection;
- better qualification;
- better contact preparation;
- better document configuration.

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
- no parallel Web/PWA/Android business-rule implementations;
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
4. Legal/Document engine
5. Web operator system
6. PWA
7. Android
8. Production operations
9. External provider activation / MAX
10. Learning loop
11. Measured scalability/team mode

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

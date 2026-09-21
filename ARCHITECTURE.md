# СХЕМА Business Platform — v1.4 Architecture Baseline

## Product boundary

Commercial Intelligence & Execution OS for one operator first, team-ready later.

Business loop:

SEARCH → INTELLIGENCE → EVIDENCE → QUALIFICATION → COMMERCIAL ACTION → ORDER → ECONOMIC RESULT → LEARNING → SEARCH IMPROVEMENT

## Runtime strategy

Start as a modular monolith. PostgreSQL is the transactional authority. External systems are adapters. Workers execute durable jobs. Services are extracted only when a measured constraint requires it.

## Layers

- `experience/` — Web/PWA/Android clients; canonical API only; no direct persistence access.
- `application/` — commands, queries, workflows, jobs and orchestration.
- `domain/` — business rules, value objects and state transitions.
- `foundation/` — identity primitives, policy, idempotency, audit, evidence, outbox, recovery, transactions.
- `adapters/` — MAX, Telegram, Email, SMS, intelligence providers, payments, documents.
- `platform/` — PostgreSQL, object storage, queue, cache, IAM, search, observability.

## Identity and truth boundary

The canonical entity is Identity, not an arbitrary company row.

Lifecycle:

RAW → CANDIDATE → IDENTIFIED → VERIFIED → ACTIVE / INACTIVE / UNKNOWN

External search results remain source observations until identity resolution. A source-side candidate reference must never be treated as a canonical identity identifier.

Critical identity resolutions:

- MATCH
- MERGE
- KEEP_SEPARATE
- QUARANTINE
- MANUAL_REVIEW

For the current Russian B2B workflow, INN is the primary cross-source deduplication key. Missing or conflicting INN data is not silently promoted to the verified working layer.

## Discovery pipeline

SEARCH → IDENTITY RESOLUTION → INTELLIGENCE → EVIDENCE → QUALIFICATION → COMMERCIAL ACTION

Search criteria are shared by all clients. Search providers may return noisy results; the canonical Search boundary validates region, industry, identifiers, source references and duplicate keys before exposing results to application workflows.

Qualification is conservative:

- unverified identity → review;
- insufficient evidence → review;
- missing contact → review;
- service mismatch → review;
- unconfirmed economic fit → review.

A record is never promoted to a critical commercial action solely because a source returned it.

## Persistence

PostgreSQL is the transactional authority.

Persistence is divided into:

- canonical identity/evidence/audit/idempotency/outbox/commercial-action/order/economic/AI-run state;
- source-side search candidate observations;
- explicit quarantine state.

Search candidate data is not canonical truth and can be superseded, expired or quarantined without corrupting Identity.

Transactional state change and outbox publication must occur atomically within one database transaction. Commercial Action, Order and Economic Entry state are also PostgreSQL-owned and traceable by source references.

External network calls never occur inside the core database transaction.

## Non-negotiable invariants

1. Identity is resolved before critical commercial action.
2. Evidence is required for externally-derived critical claims.
3. External adapters cannot mutate domain truth directly.
4. AI cannot bypass authorization, policy, evidence or economic controls.
5. Critical writes are idempotent.
6. External calls never occur inside the core database transaction.
7. Transactional state change and outbox publication are atomic.
8. Retries are at-least-once; handlers must be idempotent.
9. Uncertain or conflicting identity/evidence is quarantined or sent to review.
10. Audit records are append-only from the application perspective.
11. Configuration and business policy are versioned.
12. Self-healing may repair infrastructure/job state, never business/legal truth.
13. Web, PWA and Android share canonical API/domain semantics.
14. MAX is an adapter/channel, never a domain dependency.
15. Search results are validated before entering application workflows.
16. Source-side candidate identifiers never substitute for canonical Identity identifiers.
17. Qualification cannot silently promote unresolved or weakly evidenced data.
18. Complexity belongs inside the system, not on the operator.

## Canonical command pipeline

`Command → Authorization → Policy → Idempotency → Transaction → State Change → Outbox → Worker → External Effect → Result → Audit`

## Intelligence pipeline

`Research Policy → Research Budget → Provider Waterfall → Evidence → Qualification`

Research budgets explicitly constrain:

- provider calls;
- source count;
- token usage;
- API spend;
- elapsed time.

Provider results must include source references when they contain externally-derived claims. The intelligence application service materializes routed claims into traceable Evidence before qualification.

## AI pipeline

`Task → AI Gateway → Model/Prompt version → Evidence validation → Policy → Recommendation/Output → Audit`

AI runs record model/version, prompt version, input refs, evidence refs and usage metrics.

AI is subordinate to authorization, policy, evidence and budget controls and cannot rewrite critical business/legal truth. Validated AI runs are persisted with model, prompt, input/evidence references and usage metrics and audited without storing the generated output in audit metadata.

## MAX pipeline

`MAX → MAX Adapter → Canonical Communication Event → Application → Identity Resolution → Domain Core`

MAX API details remain isolated in the adapter. Changes in MAX API versioning, webhook structure or capabilities must not leak into the Domain Core.

## Economics lineage

`Research → Provider Cost → AI Cost → Evidence → Qualification → Commercial Action → Order → Cost → Revenue → Margin`

## v1.4 kernel workstream

The detailed 12-element kernel sequence is maintained in `docs/V1.4_KERNEL.md`. The architecture sequence below intentionally groups Order and Economics for higher-level reporting.

## v1.4 vertical slice

Current implementation sequence:

1. Foundation and architecture contract.
2. Identity resolution and global deduplication.
3. Canonical Search contract.
4. Discovery and qualification gating.
5. Transactional persistence boundary.
6. Intelligence/provider gateway.
7. AI gateway.
8. MAX adapter contract.
9. Commercial Action → Order → Economics.
10. API/PWA/Android surface and integration hardening.

## Boundary and continuity rules

- PostgreSQL is the sole transactional system of record.
- No external CRM, low-code, migration or mirror system is a platform dependency or business-rule engine.
- External providers are reachable only through explicit adapters and cannot become domain dependencies.
- MAX is included in the communication adapter boundary from the first integration design.
- Proven mature patterns are preferred over bespoke infrastructure.
- Start with one operator; preserve clean contracts for later team mode.

## Quality gate

A component is not considered complete until its contract, invariants, failure modes, tests and observability are defined.

Production readiness additionally requires:

- runtime integration tests;
- database migrations;
- security tests;
- recovery/failure drills;
- controlled deployment;
- evidence/provenance verification;
- dependency and supply-chain checks.

The architecture itself is a checked object and must remain synchronized with `architecture/contract.json`.

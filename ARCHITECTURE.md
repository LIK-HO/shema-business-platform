# СХЕМА Business Platform — v1.4 Architecture Baseline

## Product boundary
Commercial Intelligence & Execution OS for one operator first, team-ready later.

Business loop:
SEARCH → INTELLIGENCE → EVIDENCE → QUALIFICATION → COMMERCIAL ACTION → ORDER → ECONOMIC RESULT → LEARNING → SEARCH IMPROVEMENT

## Runtime strategy
Start as a modular monolith. PostgreSQL is the transactional authority. External systems are adapters. Workers execute durable jobs. Services are extracted only when a measured constraint requires it.

## Layers
- `experience/` — Web/PWA/Android clients; no direct database access.
- `application/` — commands, queries, workflows, jobs.
- `domain/` — business rules and state transitions.
- `foundation/` — identity, policy, idempotency, audit, evidence, outbox, recovery, configuration.
- `adapters/` — MAX, Telegram, Email, SMS, CRM, intelligence providers, payments, documents.
- `platform/` — PostgreSQL, object storage, queue, cache, IAM, search, observability.

## Non-negotiable invariants
1. Identity is resolved before critical commercial action.
2. Evidence is required for externally-derived critical claims.
3. External adapters cannot mutate domain truth directly.
4. AI cannot bypass authorization, policy, evidence or economic controls.
5. Critical writes are idempotent.
6. External calls never occur inside the core database transaction.
7. Transactional state change and outbox publication are atomic.
8. Retries are at-least-once; handlers must be idempotent.
9. Uncertain/conflicting identity or evidence is quarantined or sent to review.
10. Audit records are append-only from the application perspective.
11. Configuration and business policy are versioned.
12. Self-healing may repair infrastructure/job state, never business/legal truth.
13. Web, PWA and Android share canonical API/domain semantics.
14. MAX is an adapter/channel, never a domain dependency.
15. Complexity belongs inside the system, not on the operator.

## Canonical command pipeline
`Command → Authorization → Policy → Idempotency → Transaction → State Change → Outbox → Worker → External Effect → Result → Audit`

## Intelligence pipeline
`Research Policy → Research Budget → Provider Waterfall → Evidence → Qualification`

## AI pipeline
`Task → AI Gateway → Model/Prompt version → Evidence validation → Policy → Recommendation/Output → Audit`

## MAX pipeline
`MAX → MAX Adapter → Canonical Communication Event → Application → Identity Resolution → Domain Core`

## Economics lineage
`Research → Provider Cost → AI Cost → Evidence → Qualification → Commercial Action → Order → Cost → Revenue → Margin`

## v1.4 vertical slice
Identity → Search → Intelligence → Evidence → Qualification → Action.

Commercial Order/Economics are contracts in v1.4 and are implemented after the first vertical slice proves its invariants.

## Quality gate
A component is not considered complete until its contract, invariants, failure modes, tests and observability are defined. Production readiness additionally requires runtime integration tests, migrations, security tests, recovery drills and controlled deployment.

## Project continuity rules
- Airtable is legacy/transition data, not the system of record or business-rule engine.
- Replit migration remains frozen until 2026-10-13.
- Bitrix24 migration remains frozen without a scheduled date; Bitrix24 is a reference/integration target, not the core platform.
- MAX is included in the adapter boundary from the first integration design.
- Proven mature patterns are preferred over bespoke infrastructure.
- Start with one operator; preserve clean contracts for later team mode.

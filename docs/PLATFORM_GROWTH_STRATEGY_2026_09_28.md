# Shema Business Platform — Strategic Reorientation
## B2B-first intelligence core + Yandex Cloud + Bitrix24 business plane
### 2026-09-28

## 1. Strategic decision

Shema is not being developed into a second CRM, ERP, accounting or personnel-management system.

The target operating model is:

Shema intelligence core
→ search
→ identity resolution
→ evidence
→ research
→ qualification
→ contact preparation
→ business handoff
→ outcome capture
→ learning

Yandex Cloud
→ runtime
→ secrets
→ scheduled/background execution
→ managed persistence
→ observability
→ AI provider environment

Bitrix24 at mature-business stage
→ live CRM/deal/order lifecycle
→ transaction pricing and price locking
→ invoices/payments
→ business economics
→ communication history
→ assignments
→ business automation
→ team/process control

The frozen v1.4/v1.5 kernel is preserved. Order and Economics semantics already certified in the kernel remain compatibility capabilities and historical lineage; they are not a reason to expand Shema into a second operational accounting layer.

## 2. Why this is the balanced boundary

The system's strongest comparative advantage is information quality and decision support.

The expensive and failure-prone part is not calculating a margin formula; it is ensuring that the facts entering the formula are correct. If the executor, quantity, unit, price, legal status or transaction state is wrong, downstream calculation can still be internally consistent while being economically useless.

Therefore:

Shema optimizes the quality of inputs and decisions.
Bitrix24 owns the live transaction state once the opportunity is handed over.

This also reduces unnecessary retention of sensitive personnel data. The intelligence layer may need evidence that a service can be fulfilled, but it should not become a personnel or contractor database unless a separate justified capability is approved.

## 3. B2B-first operating boundary

The first commercial loop is intentionally narrow:

**B2B prospecting → qualification → contact → service delivery → repeat business → measurable unit economics**

Nothing in Shema should be added merely because a mature CRM or ERP has such a module.

### Removed from Shema

- tender/procurement subsystem;
- tender provider integrations;
- tender monitoring workspace;
- tender submission logic;
- internal document/template/configuration engine;
- document lifecycle and legal/EDO workflow relationships.

These are not deferred Shema features. They are **outside the Shema product boundary**.

### Business-plane principle

When the business reaches the corresponding maturity, live commercial operations are moved into Bitrix24. Tender/B2G becomes a separate mature-business direction implemented there or in a directly integrated specialist system. Shema does not duplicate it.

During the starting B2B period, documents are handled manually outside Shema. This is deliberate complexity control: no internal document model, version matrix, template repository or legal workflow is required to acquire, sell and learn from the first B2B transactions.

## 5. Yandex Cloud deployment strategy

### Stage YC-0 — architecture rehearsal / lowest-cost start

Use serverless components for the application shell:

- Serverless Containers for the FastAPI modular monolith;
- API Gateway as the explicit external API edge;
- Cloud Functions for narrow scheduled/triggered workers;
- Object Storage only for bounded large objects/exports;
- Container Registry for immutable application images;
- Lockbox for API keys and secrets;
- Monium for logs, metrics and traces;
- Monitoring for service health.

Yandex Cloud currently gives a free allowance for the first 1,000,000 Serverless Container invocations plus free monthly RAM/CPU allowances. This is enough for a low-traffic application shell, but it does not make the whole production stack free: Managed PostgreSQL, YandexGPT usage, external provider APIs, storage beyond free allowances and traffic can all create costs. citeturn820635search1turn820635search2turn820635search6

The timer trigger can invoke a Cloud Function on a cron schedule, with bounded retries and an optional dead-letter queue. citeturn211156search0turn211156search1

### Stage YC-1 — minimal real production

The canonical production database is an expected baseline cost once real production data exists. Other variable costs — especially AI/provider calls and observability volume — must also be budgeted explicitly.

Use Yandex Managed PostgreSQL rather than a self-managed VM when real production data begins. The service charges for compute, storage and backups while running; a stopped cluster still incurs storage/backup charges. citeturn820635search3

The reason is architectural, not convenience:

PostgreSQL remains the single transaction authority already protected by the frozen kernel.

Do not replace it with YDB merely to obtain a free tier.

YDB can be considered later as a secondary, purpose-specific high-scale component only after a measured constraint.

### Stage YC-2 — production hardening

Add only when justified:

- private networking/VPC;
- stricter IAM/service-account separation;
- production/recovery environment separation;
- staged deployments;
- backup verification in target environment;
- optional Message Queue for transport/fanout, never as a second canonical business-state authority;
- Object Storage lifecycle policies;
- cost budgets and alarms.

Message Queue may be introduced later for bounded transport workloads, but the existing PostgreSQL job/outbox mechanisms remain the business reliability authority. citeturn820635search5

### Observability rule

Do not design the platform around Cloud Logging.

Yandex Cloud states that Cloud Logging will be shut down in Q2 2027 and directs new workloads to Monium. Monium currently provides logs/metrics/traces, but its published logs/traces retention is 31 days; therefore Monium is operational telemetry, not long-term audit history. Long-lived audit and business history remain in PostgreSQL. citeturn495622search1turn495622search3turn495622search6 citeturn211156search7turn211156search9

## 6. YandexGPT

The existing YandexGPT adapter is retained.

The integration target becomes:

AI Gateway → YandexGPT adapter → Yandex Cloud AI Studio

The existing code already enforces HTTPS, bounded request/response sizes, token/cost/duration budgets, explicit production activation and provider provenance. The adapter also keeps model, prompt and evidence lineage outside provider domain semantics.

Yandex Cloud's current AI Studio documentation uses model URIs such as gpt://folder/model/latest; current Yandex tutorials explicitly use Lockbox for the API key and the yc.ai.languageModels.execute role. citeturn243840search1turn243840search5

Use YandexGPT for:

- research synthesis;
- structured extraction and classification;
- evidence summarization;
- contact preparation;
- operator assistance.

Do not use it as authority for:

- identity truth;
- legal truth;
- transaction price;
- business economics.

### Audit finding to close

YandexGPTConfiguration.max_cost currently defaults to 0.0, while validation requires a strictly positive value, and the environment default is also 0. Production activation correctly requires an explicit positive ai.yandexgpt.max_cost, but the base configuration is internally inconsistent.

This is a bounded configuration defect, not a kernel defect. Fix it before the first cloud activation rehearsal by removing the misleading zero default and requiring an explicit positive cost ceiling everywhere.

## 7. MAX

Keep the existing MAX adapter and safety boundary.

Current MAX provider evidence still does not establish provider-side idempotency or deterministic reconciliation for an ambiguous POST /messages effect. Therefore live outbound activation stays fail-closed.

MAX is currently:

adapter/channel + inbound/read surface + controlled notification path

not:

business truth + transaction authority + finance + CRM

The current repository already contains the correct safety pattern: an unsafe external effect is quarantined rather than retried optimistically.

Do not weaken that contract to make MAX available sooner.

## 8. Bitrix24 as the mature business plane

### Why Bitrix24 is a business-plane target, not a second source of research truth

Mature CRM/ERP products place live sales/order/invoice state together so that the commercial transaction has one authoritative lifecycle. Salesforce defines an order as the agreement to provision services or deliver products with known quantity, price and date; Microsoft Dynamics 365 explicitly connects opportunity → quote → order → invoice and supports locking agreed prices on live transactions; SAP exposes scheduling agreements as contractual sales structures with validity and customer responsibility. citeturn495622search5turn496805search7turn496805search11

That pattern supports the chosen boundary:

**Shema prepares and explains the opportunity. Bitrix24 executes the live business transaction after handoff.**

### Entry point

For the first single-portal integration proof, use the smallest supported Bitrix24 integration surface. At mature multi-user application scale, use an authenticated application boundary with explicit field ownership and reconciliation.

### Handoff protocol

The new `architecture/business_plane_boundary_contract.json` defines:

`PREPARED → OUTBOX_RESERVED → SENT_UNKNOWN → ACKNOWLEDGED`

with `RECONCILIATION_REQUIRED` and `HANDOFF_FAILED` as explicit failure states.

The handoff uses:
- stable `handoff_id`;
- stable idempotency key;
- mapping version;
- payload hash;
- correlation ID;
- canonical Shema identity reference;
- external Bitrix24 entity reference after acknowledgement.

A lost response is **not** permission to blindly resend. The external result must be reconciled first.

### Field ownership

Shema owns:
- identity resolution;
- evidence/provenance/freshness;
- qualification;
- contact preparation;
- repeat-business preparation;
- learning context.

Bitrix24 owns after handoff:
- live CRM/deal/order lifecycle;
- live transaction price;
- invoice/payment state;
- business economics;
- customer communication history;
- assignment/team process state;

The same live field is never written by both systems.

### Synchronization pattern

**Shema → Bitrix24**

Send only the minimum execution context:
- identity/company/contact reference;
- qualification state;
- evidence-backed reason for contact;
- contact preparation;
- repeat-business preparation;
- correlation/reference IDs.

**Bitrix24 → Shema**

Return only versioned outcome events needed for learning:
- reached/not reached;
- response class;
- qualified/rejected;
- rejection reason;
- won/lost/completed;
- repeat demand;
- operator correction;
- coarse economic outcome only when explicitly justified.

Do not mirror the full CRM or finance database.

### Repeat business

Bitrix24 already provides recurring-deal functionality that can automatically create new deals from a recurring template, with intervals and stop conditions. Therefore Shema must **not** implement a second recurring-deal engine. Shema's Phase 3A is a repeat-business preparation layer that detects, revalidates and prepares the next handoff. citeturn496805search1turn496805search5

### API / integration strategy

The integration is event-driven and ownership-based:

`Shema outbox → idempotent Bitrix command → Bitrix acknowledgement/event → Shema outcome intake → learning`

Any asynchronous transport is only a delivery mechanism. PostgreSQL remains canonical for Shema-owned state; Bitrix24 remains authoritative only for the business fields explicitly handed to it.

### Tariff/capability strategy

The current Bitrix24 catalog shows that plan capabilities differ materially: recurring deals and online payments are on Basic, invoices/estimates on Standard, while deeper automation/analytics appear on higher plans. Therefore the integration must use **capability detection**, not a hard-coded assumption that every portal has every feature. citeturn402426search0turn402426search1

When a capability is unavailable:
- Shema keeps the preparation state;
- the operator receives an explicit `CAPABILITY_UNAVAILABLE` state;
- Shema does not silently recreate the missing CRM/accounting feature as a competing subsystem.

### Reconciliation

A mature integration requires:
- periodic reconciliation of handoff IDs ↔ Bitrix24 entity IDs;
- mapping-version checks;
- detection of orphaned/duplicated external entities;
- quarantine of ownership mismatches;
- append-only handoff/outcome history.

## 8A. Data-plane continuity and operator causality

### Where the databases live

**Yandex Cloud / Shema**
- Managed PostgreSQL is the canonical database for Shema-owned intelligence, identity, evidence, provenance, handoff lineage and learning context.
- Object Storage holds only bounded large evidence objects/exports where required.
- Monium is operational telemetry; durable audit/history stays in PostgreSQL.

**Bitrix24**
- Bitrix24 maintains its own business-plane storage according to the selected deployment model.
- After handoff, Bitrix24 owns the live deal/order/process state explicitly transferred to it.

The transition is **not** a wholesale migration of the Shema database into Bitrix24.

### Operator continuity

The operator sees one causal workflow:

**Shema dossier → prepared handoff → Bitrix24 deal/entity → live work → outcome → Shema learning context**

The handoff carries stable Shema identity reference, handoff ID, integration correlation ID, Bitrix24 entity reference, mapping version and snapshot/payload reference.

For multiple operators:
- before handoff, Shema may own preparation assignment;
- after handoff, Bitrix24 owns live assignment, team queues, tasks, approvals and transaction activity;
- Shema does not keep a parallel live-order board;
- stale writes are rejected by revision/ownership controls;
- every assignment/reassignment is attributable to an actor.

This prevents one operator from continuing against a stale Shema record while another changes the live transaction in Bitrix24.

## 9. Economics and Order Boundary

### Order — simple explanation

Inside the frozen kernel, **Order is a compatibility model**: customer/order reference, line items, quantity, unit price and lifecycle.

It is useful because the core was certified around that business model and existing historical lineage should not be destroyed.

It is **not** the target operational order system.

After Bitrix24 handoff:
- Bitrix24 owns the live order/deal;
- Bitrix24 owns current price and transaction status;
- Bitrix24 owns invoice/payment progression and business economics;
- Shema keeps the preparation context and the reference needed for learning.

This is consistent with mature sales platforms where quote/order/invoice form a controlled transaction lifecycle rather than being split between unrelated authorities. citeturn496805search0turn496805search7

### Economics — simple explanation

Inside the frozen kernel, **Economics** is a traceable calculation/lineage capability: cost and revenue entries can be summed into a deterministic gross-margin result.

That model is retained for compatibility and history.

But it must not be mistaken for:
- accounting;
- tax accounting;
- payment reconciliation;
- payroll;
- authoritative profitability reporting;
- operational cost allocation.

Bitrix24, or a connected finance/ERP/EDO/accounting system, owns those live business meanings once the transaction crosses the handoff boundary.

Shema should receive only the **minimum outcome features** needed to learn:
- won/lost/completed;
- repeat demand;
- optional coarse revenue/cost/margin bands or normalized outcome classes;
- source/provider quality;
- operator corrections.

Exact financial ledgers do not need to be mirrored into Shema by default.

### Critical rule

If a future feature requires Shema to calculate an authoritative live price, margin, invoice, payment state or fulfillment cost, that feature is **outside the current product boundary** and requires a separate architecture decision.

## 10. Learning without importing confidential business machinery

The learning loop should be outcome-oriented.

Prefer:

feature/context → action → result class → correction → future policy

over:

entire CRM database → black-box training

The first wave of feedback can be categorical and low-risk:

- contacted;
- no answer;
- wrong contact;
- need confirmed;
- not relevant;
- price objection;
- documents requested;
- deal won/lost;
- repeat demand observed.

Detailed financial or personnel data enters Shema only if a separate business case proves it is necessary.

## 11. Revised implementation order

1. Finish intelligence/search/research quality.
2. Complete contact preparation and Repeat Business Preparation.
3. Build the unified Web/PWA surface with public client intake and protected operator workspace.
4. Put the same public Web application inside a MAX bot as a mini-app projection.
5. Move the proven modular monolith to Yandex Cloud with Managed PostgreSQL as the canonical Shema database.
6. Introduce Bitrix24 as the mature business-control plane with explicit handoff, ownership and reconciliation.
7. Keep customer-facing MAX communication bounded and tied to the same public client context.
8. Feed low-risk commercial outcomes back into Shema.
9. Scale only from measured bottlenecks.

## 12. Global architectural verdict

The balanced target is not:

Shema + CRM + ERP + HR + accounting + AI + messenger

It is:

Shema = intelligence and decision-support core

Yandex Cloud = controlled runtime

Bitrix24 = mature business execution/control plane

external providers = replaceable evidence/communication adapters

YandexGPT = bounded reasoning/processing service

MAX = guarded communication adapter

This preserves the project's strongest property: complexity is concentrated inside reliability and evidence controls, while the operator sees a small number of useful decisions and actions.

No additional CRM/ERP/HR/accounting subsystem is justified inside Shema. No new database authority or microservice split is justified either.
## 8B. Public Intake and Counterparty Preflight

The public acquisition surface uses a two-speed model:

**fast deterministic preflight** → **deeper operator research when needed**.

At form time, the system collects only the minimum request data and conditionally asks for INN/OGRN/OGRNIP. Identifier syntax is validated locally before any provider call. Official FNS/EGRUL/EGRIP evidence is resolved server-side; GPT is not used as a registry lookup engine or legal-status oracle.

The client receives only minimal actionable feedback: identifier mismatch, registered/active, liquidation/termination/reorganization signal, not found, or provider-unavailable. The operator receives the richer evidence-linked preflight card with source, snapshot date/freshness, contradictions, relevant business fields, attention/blocking facts and unknowns.

The operator's work-acceptance decision remains human-owned. The platform does not replace the decision with an opaque AI score.

## 8C. Public Form Security and Resource Protection

Public form traffic is treated as hostile/untrusted input. The defense is layered:

- edge WAF/rate limiting and bot challenge;
- server-side schema and size validation;
- separate submission and registry-lookup budgets;
- idempotency and duplicate-fingerprint protection;
- cache reuse for repeated identifier checks;
- anti-enumeration controls and minimal public responses;
- bounded provider timeouts/retries and a feature kill switch;
- attachment upload kept disabled until a private quarantine boundary is verified.

The browser never carries FNS integration credentials, Bitrix24 credentials or AI provider secrets. The browser calls only the canonical Shema API.

## 8D. Controlled Evolution Mechanism

Every new public ingress, provider, external effect, security boundary, material quota/cost change, migration or cross-system ownership change is admitted through `architecture/platform_evolution_contract.json`.

The standard path is:

`OBSERVE → PROBLEM_STATEMENT → BOUNDARY_CONTRACT → GLOBAL_IMPACT_REVIEW → THREAT_AND_ABUSE_MODEL → RESOURCE_AND_COST_MODEL → VERTICAL_SLICE → NEGATIVE/RECOVERY → INTEGRATION/E2E → ADVERSARIAL_GATE → CONTROLLED_RELEASE → MEASURE → LEARN → FREEZE_OR_AMEND`.

Public ingress/provider changes are classified E2; persistence-authority or cross-system ownership changes are E3; frozen-kernel semantic changes are E4 and require the separate core exception process.
## 8E. Temporary Repeat Orders Before Bitrix24

Before Bitrix24 is active as the live business plane, Shema is permitted a bounded local repeat-order mode using the frozen Order/Economics semantics.

The local operator flow is:

Previous completed order → Revalidate client/evidence/current assumptions → Create new repeat order → Execute → Record result

The previous order remains immutable. The new order receives its own idempotency key, lineage reference and transaction-scoped economics.

Once Bitrix24 becomes live, the transition is not a copy followed by immediate deletion. It is:

Freeze → Snapshot → Bitrix create/acknowledge → Full readback → Completeness proof → Recovery verification → Purge live Shema rows → Freeze minimal lineage → Hide obsolete UI capability

This guarantees that deleting operational rows is the last step of a verified migration, not part of the migration attempt.

## 8F. Public Intake Data Plane

Raw website/MAX request data is stored in a dedicated PostgreSQL database behind the canonical API. This database has separate credentials, access policy, backup/recovery scope and an intake outbox.

The purpose is isolation:

- the public edge cannot write the canonical Shema DB directly;
- a temporary Shema outage cannot destroy an accepted request;
- intake notifications can be retried independently;
- raw form data can be purged according to a versioned retention policy without restructuring Shema's intelligence database.

The operator sees a durable **Новые заявки** queue and notification center. The notification layer is derived from durable intake events, not browser state.

## 8G. Counterparty Verification & Monitoring

The lead-search field now acts as a dual-mode operator tool.

When the value matches an exact INN/OGRN/OGRNIP:
- canonical search enters COUNTERPARTY_CHECK;
- deterministic registry verification runs first;
- the operator may request bounded deep research;
- the counterparty may be saved to **Мониторинг** or **Избранные**.

The operator workspace is:

**Контрагенты → Проверка | Мониторинг | Избранные**

Monitoring is separate from favorites. Favorites are personal shortcuts; monitoring creates scheduled registry snapshots, change events and notifications.

AI is optional after the deterministic evidence packet. It can explain what changed, but it cannot create or approve the underlying change event.


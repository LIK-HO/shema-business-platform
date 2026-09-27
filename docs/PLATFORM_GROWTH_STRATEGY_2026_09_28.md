# Shema Business Platform — Strategic Reorientation
## Yandex Cloud foundation + provider-neutral procurement + Bitrix24 business plane
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
→ procurement intelligence
→ contact preparation
→ document/context preparation
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

## 3. Procurement architecture correction

### Rejected direction

B2B-Center is removed from the roadmap as a named strategic provider.

The architecture must not depend on a single commercial ETP.

### Adopted direction

Build one provider-neutral procurement source registry and adapter boundary.

The internal model is:

ProcurementSourceRegistry
→ Source Adapter
→ Normalized Procurement Observation
→ Change/Freshness layer
→ Identity/Evidence
→ Qualification
→ Contact reason

Each provider exposes capabilities rather than owning domain semantics.

### Provider portfolio

| Layer | Provider | Role | Status |
|---|---|---|---|
| Official baseline | ГосПлан API v2 / ЕИС-origin data | public procurement observation | foundation already verified |
| Aggregation | TenderGuru API | broader state/corporate/commercial coverage, contracts/docs/risk-oriented enrichment | first candidate, not yet activated |
| Specialized | future providers | narrow coverage gaps only | evidence-gated |

TenderGuru's current API documentation publishes multiple procurement/data sections and a tiered API offer; its current published API Start plan is 150,000 requests/month for 10,000 RUB/month. This makes it a growth-stage aggregation option rather than a free foundation. citeturn820635search11

The free/minimal path therefore remains:

GosPlan test → verified deterministic fixtures → controlled production GosPlan later

and only then:

measured coverage gap → TenderGuru adapter

No provider is silently substituted when another fails.

## 4. Universal procurement adapter contract

Every source adapter must declare:

- source class;
- supported observation types;
- supported filters;
- pagination/cursor semantics;
- rate limits;
- authentication;
- timeout and error semantics;
- response-size limits;
- freshness characteristics;
- provenance requirements;
- cost budget;
- capability gaps.

Provider-specific fields remain inside the adapter or an explicit extension payload.

The normalized observation always preserves:

provider_id + external_id + source_ref + observed_at + provenance + observation_type

Cross-source identity resolution happens only after normalization, using the existing Identity/Evidence rules.

This permits the system to combine official-origin observations with commercial aggregation later without turning either provider into a second CRM.

## 5. Yandex Cloud deployment strategy

### Stage YC-0 — architecture rehearsal / lowest-cost start

Use serverless components for the application shell:

- Serverless Containers for the FastAPI modular monolith;
- API Gateway as the explicit external API edge;
- Cloud Functions for narrow scheduled/triggered workers;
- Timer trigger for procurement polling;
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
- durable procurement scheduler state in PostgreSQL;
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
- procurement observations;
- contact preparation;
- repeat-business preparation;
- document requirement/configuration snapshots;
- learning context.

Bitrix24 owns after handoff:
- live CRM/deal/order lifecycle;
- live transaction price;
- invoice/payment state;
- business economics;
- customer communication history;
- assignment/team process state;
- final business-document execution where configured.

The same live field is never written by both systems.

### Synchronization pattern

**Shema → Bitrix24**

Send only the minimum execution context:
- identity/company/contact reference;
- qualification state;
- evidence-backed reason for contact;
- procurement context;
- contact preparation;
- repeat-business preparation;
- document requirement snapshot;
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

1. Close the current procurement foundation without activating external production traffic.
2. Implement procurement durable runtime as one bounded vertical slice:
   source registry → adapter → durable watch → evidence → operator queue.
3. Keep ГосПлан as the first real procurement activation.
4. Add TenderGuru only after measured source-coverage evidence shows a gap.
5. Complete contact preparation.
6. Implement Repeat Business Preparation only; do not reimplement Bitrix recurring deals.
7. Implement Document Configuration & Handoff Preparation; final issuance/signing/storage stays in the business/EDO plane.
8. Build Web/PWA over the proven workflows.
9. Deploy the modular monolith to Yandex Cloud with Managed PostgreSQL as the production canonical database.
10. Activate YandexGPT through the existing provider-neutral gateway and cloud secret boundary.
11. Introduce Bitrix24 integration as a separate business-plane boundary with explicit field ownership.
12. Keep MAX live outbound gated until its provider-side safety evidence changes.
13. Feed low-risk commercial outcomes back into Shema.
14. Scale infrastructure only from measured bottlenecks.

## 12. Global architectural verdict

The balanced target is not:

Shema + CRM + ERP + HR + tender system + accounting + AI + messenger

It is:

Shema = intelligence and decision-support core

Yandex Cloud = controlled runtime

Bitrix24 = mature business execution/control plane

external providers = replaceable evidence/communication adapters

YandexGPT = bounded reasoning/processing service

MAX = guarded communication adapter

This preserves the project's strongest property: complexity is concentrated inside reliability and evidence controls, while the operator sees a small number of useful decisions and actions.

No new database authority, microservice split, tender submission, personnel system or duplicate accounting engine is justified by this strategy.

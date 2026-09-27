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
→ live commercial transactions
→ pricing used for transactions
→ orders/deals
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

Yandex Cloud currently gives a free allowance for the first 1,000,000 Serverless Container invocations and 10 GB×hour RAM plus 5 vCPU×hour per month; Object Storage also has monthly free allowances. citeturn820635search1turn820635search2turn820635search6

The timer trigger can invoke a Cloud Function on a cron schedule, with bounded retries and an optional dead-letter queue. citeturn211156search0turn211156search1

### Stage YC-1 — minimal real production

The one unavoidable production cost is the canonical PostgreSQL layer.

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

Message Queue currently provides 100,000 queue requests/month free, which makes it useful later for bounded transport workloads, but the existing PostgreSQL job/outbox mechanisms remain the business reliability authority. citeturn820635search5

### Observability rule

Do not design the platform around Cloud Logging.

Yandex Cloud currently states that Cloud Logging will be shut down in Q2 2027 and directs new workloads to Monium; the published comparison also shows Monium's current lower log-ingestion price and 31-day log TTL. citeturn211156search7turn211156search9

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

### Entry point

For a single Bitrix24 portal, an inbound webhook is appropriate for the first integration proof; Bitrix24 explicitly documents webhooks for simple integrations and single-account scenarios. For the mature multi-user application boundary, use OAuth 2.0. citeturn676125search0turn676125search4turn676125search6

### Synchronization pattern

Shema → Bitrix24

Send only the handoff package needed to operate the opportunity:

- canonical identity reference;
- company/contact reference;
- qualification state;
- evidence-backed reason for contact;
- procurement context;
- contact preparation;
- dossier link/reference;
- correlation/reference IDs.

Bitrix24 → Shema

Return only the outcome data needed for learning:

- contact reached / not reached;
- response classification;
- qualified / rejected;
- reason for rejection;
- deal won/lost;
- repeat-business signal;
- selected correction/feedback;
- minimal outcome timestamps.

Do not copy the full CRM or finance database back into Shema by default.

### Field ownership

A field has one owner.

There are no unconstrained two-way writes to the same live field.

This is the critical protection against divergent price, responsible-person, stage or economic data.

Bitrix24 is the owner of live business-process fields after handoff. Shema remains the owner of research, evidence and intelligence fields.

### API mechanics

Bitrix24 supports inbound/outbound webhooks, OAuth 2.0, event handlers and batch REST calls. A batch can contain up to 50 subrequests. citeturn676125search1turn676125search6turn676125search9

The integration should therefore use:

Shema outbox → idempotent Bitrix command → Bitrix event → Shema outcome intake → learning

with explicit reconciliation.

### Tariff progression

Bitrix24 currently has a Free plan with basic CRM and a Basic plan that adds recurring deals and other expanded CRM functionality; higher plans add invoices/estimates, automation, analytics and deeper business-process tooling. Exact feature availability must be checked against the account's current plan before each activation. citeturn820635search4

The architecture does not depend on a specific tariff. The integration contract must degrade by capability rather than duplicate the missing function inside Shema.

## 9. Economics and order boundary

New development in Shema must not expand live:

- price calculation;
- margin calculation;
- invoice/payment accounting;
- executor payroll/personnel management;
- transaction accounting;
- detailed fulfillment economics.

The frozen kernel keeps its existing Order/Economics objects because removing them would violate the certified core boundary and historical lineage.

The product strategy changes their role:

compatibility/history/learning evidence — yes
new operational accounting platform — no

At mature stage:

Bitrix24 → live commercial state and economics

Shema → evidence that helps improve future decisions

This is the correct separation between an intelligence system and a transaction-control system.

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
6. Implement the Repeat Customer Order Engine only as preparation/orchestration; do not turn Shema into the accounting owner.
7. Complete document configuration.
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

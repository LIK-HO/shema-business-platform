# Shema — Adversarial Architecture & Business Strategy Review
## 2026-09-28

## Review stance

This review deliberately assumes an adversarial objective: find ways to make the system duplicate truth, produce false confidence, lose data, create unrecoverable external effects, accumulate unnecessary cost, capture unnecessary confidential data, or become too complex for a one-operator business.

The review covered:
- frozen v1.4 kernel and post-core v1.5 boundaries;
- Search / Intelligence / Evidence / Qualification;
- Procurement foundation;
- Order / Economics;
- YandexGPT;
- MAX;
- Yandex Cloud deployment strategy;
- Bitrix24 handoff strategy;
- repeat business;
- document configuration;
- learning loop;
- current runtime composition;
- architecture contracts and tests;
- latest PR/CI state.

The repository was not treated as correct merely because the existing CI had previously been green. The current HEAD and newly introduced strategic contracts were reviewed separately.

## 0A. Global mandatory survival gate

This review establishes a permanent rule: every material strategy change and every element completion triggers a new adversarial review of the entire approved architecture before VERIFIED/CLOSED.

The review attempts professional system destruction, not local confirmation. It searches for:
- split-brain authority;
- broken operator causal continuity;
- multi-operator stale writes and assignment conflicts;
- provider failure/lock-in;
- migration and rollback traps;
- cost/quota cascades;
- unsafe external effects;
- legal/EDO obsolescence;
- recovery failure.

The machine-readable contract is architecture/global_adversarial_survivability_gate_contract.json. The development protocol makes the gate a closure requirement for the current HEAD.

The target is architectural survivability: preserve canonical truth, contain impact, recover deterministically, audit and learn. Literal zero failure is not assumed.


---

## Executive conclusion

The global strategy is sound **after the boundary corrections made during this review**, but it is not yet ready for production execution.

The strongest architecture is:

**Shema = intelligence, evidence, preparation and learning**

**Yandex Cloud = controlled runtime/infrastructure**

**Bitrix24 = mature live business-control plane**

**External providers = replaceable adapters**

**YandexGPT = bounded processing**

**MAX = guarded communication adapter**

The core reason is structural: mature sales platforms keep the live transaction lifecycle together. Salesforce treats Orders as agreements with known quantity, price and date; Microsoft Dynamics 365 connects opportunity → quote → order → invoice and can lock agreed transaction pricing; SAP exposes scheduling agreements as contractual sales structures. This supports keeping live order/pricing/payment/economic authority together instead of splitting it between the intelligence system and CRM/business system.

---

# 1. Order and Economics — final boundary

## 1.1 Order inside the frozen kernel

Order is retained because it is already a certified kernel element.

In simple terms it means:

> “We have a structured business-order object with customer reference, lines, quantities, prices and lifecycle.”

It is useful for:
- compatibility;
- historical lineage;
- deterministic internal tests;
- old business-flow integrity;
- future learning references.

It must not become the operator's primary live order system.

## 1.2 Bitrix24 owns the live transaction after handoff

After the business opportunity is handed to the mature business plane:

- Bitrix24 owns live deal/order status;
- Bitrix24 owns the current transaction price;
- Bitrix24 owns invoice/payment state;
- Bitrix24 owns business process stages;
- Bitrix24 owns current customer-facing transaction communication;
- Bitrix24 owns live business economics within the chosen business/accounting configuration.

Shema keeps:
- preparation context;
- evidence;
- provenance;
- identity references;
- handoff lineage;
- outcome features needed for learning.

The same live field must never be editable by both systems.

## 1.3 Economics inside the frozen kernel

Economics currently means a deterministic traceable calculation over recorded cost/revenue entries.

This is not a substitute for:
- bookkeeping;
- tax accounting;
- payroll;
- payment reconciliation;
- authoritative profitability;
- operational cost allocation;
- inventory costing;
- finance controls.

It remains for:
- compatibility;
- historical lineage;
- controlled internal analytical semantics.

No new live accounting subsystem is to be built in Shema.

---

# 2. Findings

Severity definitions:

- **P0** — could create a fundamental business/data integrity failure.
- **P1** — high-impact architectural or operational weakness.
- **P2** — medium risk; must be controlled before corresponding maturity stage.
- **P3** — optimization/documentation issue.

| Finding | Severity | Status | Required action |
|---|---|---|---|
| Ambiguous ownership between Shema and Bitrix24 | P0 | Fixed | Explicit business-plane boundary contract |
| External handoff lacked a formal failure/reconciliation state machine | P0 | Fixed | Stable handoff ID, outbox, idempotency, reconciliation |
| Repeat-order design could duplicate Bitrix recurring-deal functionality | P1 | Fixed | Phase 3A renamed Repeat Business Preparation |
| Internal document engine would have turned Shema into a second legal/business system | P1 | REMOVED | Document subsystem deleted from Shema boundary |
| Procurement subsystem increased unnecessary complexity for the first B2B stage | P1 | REMOVED | Procurement code/contracts/tests deleted from Shema |
| Document/tender expansion created avoidable dependency surface | P1 | REMOVED | Both capability tracks removed from Shema |
| YandexGPT had an invalid implicit zero cost ceiling | P1 | Fixed | Explicit positive cost configuration required |
| Bitrix24 plan capabilities differ materially | P1 | Fixed at strategy level | Capability detection, no hidden reimplementation |
| Monium could be mistaken for long-term audit storage | P1 | Fixed at strategy level | PostgreSQL remains durable audit/business history |
| Customer communication ownership after handoff was ambiguous | P1 | Fixed | Bitrix24/business plane owns customer-facing execution/history |
| Early tender runtime would create an unnecessary second business surface | P1 | REMOVED | No tender runtime exists in Shema |
| Bitrix24 production runtime integration is still absent | P1 | Open by design | Separate handoff/adapter phase |
| Outcome-learning schema is not yet a full runtime vertical slice | P1 | Open | Versioned outcome contract + reconciliation + privacy controls |
| Source coverage quality is not yet measured against realized business outcomes | P1 | Open | Coverage/precision/revenue-quality benchmark before aggregation expansion |
| Commercial tender-provider expansion | P2 | REMOVED | No tender provider is part of the Shema product |
| Live MAX outbound remains blocked | P1 | Correctly blocked | Do not weaken safety gate |
| Full latest CI gate has not yet closed | P0 for release status | Pending | Do not declare the current boundary verified |

---

# 3. Hidden weakness: split-brain business state

The most dangerous long-term failure mode is not a provider outage.

It is this:

**Shema says price = 14,000 ₽**

while

**Bitrix24 says price = 16,000 ₽**

or:

**Shema says order is active**

while

**Bitrix24 says cancelled**

or:

**Shema calculates margin using one executor/cost**

while

**Bitrix24 executes another configuration**.

A system can be technically healthy and still be economically wrong.

The new contract prevents this by giving one live field one owner.

The handoff itself does not delete Shema history. It establishes a business-domain boundary.

---

# 4. Handoff failure model

External integration cannot be treated as:

`POST → 200 → done`

The dangerous state is:

`request sent → Bitrix24 changed state → response lost`

A retry can create a duplicate business entity.

Therefore the handoff now requires:

`PREPARED → OUTBOX_RESERVED → SENT_UNKNOWN → ACKNOWLEDGED`

or:

`SENT_UNKNOWN → RECONCILIATION_REQUIRED`

Unknown external effects are never blindly replayed.

This follows the same general reliability principle already used in the frozen commercial-send workflow: local state must be durable before the external effect, and ambiguous external outcomes require reconciliation.

---

# 5. Repeat business

Bitrix24 already has recurring deal templates that generate new deals on a configured schedule. That means a custom full recurring-deal engine inside Shema would be unnecessary duplication.

The optimized boundary is:

**Shema**
→ notices repeat pattern
→ checks evidence/freshness
→ prepares next-business context
→ prepares handoff

**Bitrix24**
→ creates/owns the real recurring or repeat deal
→ owns the current transaction
→ executes the commercial process

This is simpler and more reliable.

---

# 6. Removed capability tracks

The adversarial review caused two complexity-reduction decisions:

- no internal document/template/legal workflow module in Shema;
- no procurement/tender module, provider integration or tender workspace in Shema.

Both were removed from the active repository surface. The later business plane may solve its own operational needs independently, but Shema has no dependency on them.


# 8. Yandex Cloud

The chosen serverless-first strategy is structurally appropriate for a one-operator launch.

Current Yandex Cloud documentation provides free monthly allowances for Serverless Containers, including the first 1,000,000 invocations plus RAM/CPU allowances, while Managed PostgreSQL remains a separately billed managed service. citeturn495622search0turn495622search4

The important correction is:

**“serverless free allowance” ≠ “whole platform is free”.**

Real cost drivers include:
- PostgreSQL;
- YandexGPT usage;
- external APIs;
- storage;
- egress;
- observability.

So cost-control must be part of the architecture rather than an afterthought.

---

# 9. Observability and audit

Yandex Cloud states Cloud Logging will be shut down in Q2 2027 and recommends Monium. Monium provides logs, metrics and traces, but its published retention for logs/traces is 31 days. citeturn495622search1turn495622search3turn495622search6

Therefore:

**Monium = operational observability**

**PostgreSQL = durable audit/business history**

Never use operational telemetry as the legal/business historical record.

---

# 10. Bitrix24 capability drift

Bitrix24's current plans differ substantially. Current published plan information places recurring deals and online payments on Basic, invoices/estimates on Standard, with deeper automation/analytics on higher plans. citeturn402426search0turn402426search1

This creates an easy failure mode:

> “The integration assumes feature X exists because it exists in the architecture.”

It may not exist on the active portal.

The correct tactic is capability detection:

`available → use capability`

`unavailable → preserve preparation state and expose explicit capability-unavailable status`

Never recreate missing Bitrix functionality inside Shema merely to hide a plan limitation.

---

# 11. Learning loop — biggest remaining strategic risk

The next hidden risk is data feedback.

If Shema receives the entire Bitrix24 database and learns from it indiscriminately, it can start learning:

- CRM process artifacts;
- operator habits;
- temporary price anomalies;
- incorrect fields;
- accounting corrections;
- biased rejection reasons;
- outdated responsibilities;
- accidental labels.

This can make the “learning” system progressively worse while appearing more intelligent.

The safer pattern is:

`context → action → outcome class → correction → future policy`

with:
- versioned outcome semantics;
- stable external event ID;
- append-only historical outcomes;
- corrections represented as new events;
- minimal data import;
- coarse financial features unless exact figures are demonstrably necessary.

This is not yet fully implemented as a runtime vertical slice and should become its own controlled boundary.

---

# 12. B2B-first scope protection

The first commercial stage is deliberately B2B. Anything that would turn Shema into a second operational business platform is rejected unless a measured constraint proves it necessary.

The later business plane is a separate system boundary. Shema does not implement tender/procurement execution inside that boundary.


# 13. Security / privacy regression

A major advantage of the revised boundary is reduced sensitive-data collection.

Shema should not evolve into a personnel database containing:
- passport details;
- personal contact history beyond necessity;
- payroll data;
- extensive executor dossiers;
- unrelated personnel attributes.

For learning, the system normally needs:

> “Can this service be fulfilled and what was the outcome?”

not:

> “Keep a complete private dossier on every executor.”

This materially lowers the blast radius of a breach.

---

# 14. MAX

The current block is correct.

Do not attempt to bypass it with:
- automatic retry;
- alternate undocumented endpoint;
- shadow deduplication;
- hidden provider fallback.

A customer-facing MAX message after Bitrix24 handoff also needs a business-plane ownership decision, not merely a transport safety decision.

Until both are solved:

**MAX = guarded adapter, not authoritative customer-communication history.**

---

# 15A. Public Web/PWA/MAX attack surface

The new public surface is deliberately one application, not a second platform:

**Advertising/direct traffic → public Web → request form → canonical API → request observation → operator → Bitrix24 after handoff**

MAX is a projection of that same public Web application inside a MAX bot. The mini-app must not introduce a second database or separate business rules. MAX bot conversations may answer questions and guide the customer, but authoritative live transaction state remains on the server/business plane.

New adversarial checks therefore include:
- duplicate form submission after timeout or refresh;
- spam/automation and attachment abuse;
- forged UTM/referral attribution;
- request creation without valid server-side validation;
- MAX start-parameter tampering;
- cross-user access to another customer's request;
- public endpoint accidentally bypassing operator/business authorization;
- domain/DNS cutover breaking mail or HTTPS.

The public surface becomes a new trust boundary, so its inputs are observations, never canonical business truth by themselves.

# 15. Positive findings

The adversarial review also found important strengths:

### Frozen core discipline
The repository strongly separates frozen v1.4 semantics from post-core capabilities.

### Modular monolith
The current architecture avoids premature microservice decomposition.

### Identity/evidence boundary
External observations are not silently promoted into canonical truth.

### External-effect safety
Commercial send already has durable reservation, lease and idempotency semantics.

### Recovery
The core has executable backup/recovery/PITR evidence.

### Runtime composition
The current Yandex runtime composition exposes AI/search capabilities while Order/Economics are not composed into that runtime. This is a useful existing protection against accidental live business execution.

### Provider safety
MAX and external provider execution are fail-closed rather than “activated because the API exists”.

These are real strengths worth preserving.

---

# 16. Final optimized strategy

### Phase A — intelligence

**Search → Identity → Evidence → Research → Qualification → Contact Preparation → Repeat Business Preparation**

### Phase B — public acquisition and operator surface

**Public Web/PWA → advanced client request → operator workflow → MAX mini-app projection**

### Phase C — business handoff

**Business Plane Handoff → Bitrix24**

with idempotency, outbox, reconciliation, explicit ownership and multi-operator continuity.

### Phase D — live business execution

Bitrix24 owns the live commercial process:

**Deal → Order → Pricing → Invoice → Payment → Economics → Communication → Fulfillment**

### Phase E — learning

**Outcome → Correction → Search/Research improvement**

### Phase F — measured scale

Only after actual measurements justify it: queues, caches, service extraction, team mode and specialized infrastructure.

# 16A. Database and operator continuity

Yandex Cloud Managed PostgreSQL remains the canonical Shema database. Bitrix24 owns its own live business-plane data after handoff. The full Shema database is not migrated into Bitrix24.

The causal chain remains:

**Shema intelligence → handoff → Bitrix24 live process → outcome → Shema learning**

Stable references preserve continuity across the two systems.

# 17. Release verdict

The **global strategy now passes the conceptual adversarial review** with the corrected boundaries.

The **current implementation does not yet pass final release review**, because the latest HEAD still requires the complete release-gate CI to close after the new corrections.

The three most important next executable boundaries are:

1. **Business-plane handoff runtime** — Bitrix24 adapter, idempotent outbox, reconciliation and field-ownership enforcement.
3. **Outcome learning vertical slice** — minimal, versioned, privacy-preserving result feedback.

No additional CRM/ERP/economics/HR subsystem should be added to Shema.
---

# 15B. Public Intake Trust Boundary — Current Adversarial Review

## Changed boundary
The public request form is an untrusted ingress surface. It does not create live business state and does not call Bitrix24, registry providers or AI directly from the browser.

The approved causal chain is:

**public Web/MAX mini-app → edge security → canonical API → deterministic identifier validation → official-registry preflight → idempotent request observation → operator review → qualification → Bitrix24 handoff**

## Destruction hypotheses

| Failure hypothesis | Severity | Control / disposition |
|---|---|---|
| Automated traffic floods submissions and exhausts application capacity | P1 | Edge WAF/rate limit + bot challenge + bounded request body + application limits + quarantine |
| Attackers turn INN/OGRN lookup into a registry enumeration oracle | P1 | Separate lookup budget, cache, anti-enumeration, progressive challenge and minimal public responses |
| Invalid identifiers or repeated lookups amplify provider cost | P1 | Deterministic checksum/type validation first; no GPT; bounded provider budget; cache reuse |
| A client resubmits after a timeout and creates duplicate observations | P1 | Idempotency key, payload fingerprint, same-key convergence, different-payload fail-closed, reconciliation on ambiguity |
| Public input bypasses canonical authorization and creates a live Bitrix entity | P0 | Direct browser→Bitrix forbidden; public form creates only a server-authoritative request observation |
| Registry provider outage is interpreted as a verified clean counterparty | P1 | Explicit UNKNOWN/PROVIDER_UNAVAILABLE state; no fabricated status |
| Raw registry data is leaked to a public browser | P1 | Minimal public response; detailed evidence only in protected operator surface |
| Cache poisoning changes a future counterparty result | P1 | Server-only cache writes, source/version/snapshot metadata and provider-bound evidence lineage are required |
| Attachments become malware/storage/DoS path | P1 | Attachments disabled until private quarantine upload, MIME/size validation and scanning boundary is verified |
| AI becomes an implicit counterparty verdict authority | P1 | Deterministic evidence precedes AI; AI cannot author registry truth or acceptance decision |
| Evolution mechanism allows new providers to bypass review | P1 | E2 admission gate, resource/security model, provider exit path, adversarial gate and current-head CI required |

## Split-brain check

- Public Web owns no live transaction state.
- FNS-derived preflight is evidence, not a second business authority.
- Shema owns request observation and intelligence context.
- Bitrix24 owns live business state only after acknowledged handoff.
- No same live field is dual-written.

## Operator causal chain

`request_id → correlation_id → preflight_snapshot_id → identity/evidence → operator acceptance decision → handoff_id → bitrix_entity_ref → outcome`

## Recovery / rollback

- Disable public intake without changing the kernel.
- Disable external registry lookup while continuing to accept requests with explicit UNKNOWN verification state.
- Tighten edge limits without changing canonical persistence semantics.
- Retire a provider without changing the request observation model.
- No public-ingress migration is allowed without a controlled cutover and rollback state.

## Verdict

The boundary is **architecturally survivable and bounded**, but it is not release-closed until the implementation and current-head full release-gate CI prove the contract.

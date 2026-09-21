# Production Payment & Settlement Boundary

## Boundary

The v1.4 kernel ends at Economics and the canonical API/experience boundary. Production money execution is a post-kernel runtime contour and must not redefine kernel semantics.

The canonical flow is:

Order → Payment Intent → Payment Attempt → Provider Effect → Verified Provider Event → Payment State → Economic Entry → Settlement Expectation → Provider Statement → Reconciliation → Settlement Close

PostgreSQL remains authoritative for platform payment and reconciliation state. A payment provider is authoritative only for externally observed provider facts that enter through a verified adapter.

## Records

### Payment Intent

Expected payment linked immutably to an Order. It owns explicit amount, currency, stable platform payment identifier, idempotency context and current state.

### Payment Attempt

One concrete provider effect. It owns attempt number, stable external idempotency key, provider reference, request/response times and lease ownership while an external effect is in flight.

### Verified Provider Event

Inbound provider observation with immutable provider event identifier, normalized event type, verified signature/authentication result, received timestamp, payload reference and processing state.

Duplicate delivery of an already processed provider event is a no-op.

### Settlement Record

Provider settlement fact with settlement identifier, immutable statement hash, covered payment references, gross amount, fees, net amount, currency, settlement timestamp and reconciliation state. Each statement line is persisted immutably with a provider payment reference and amount.

### Reconciliation Item

Durable discrepancy between platform expectation and provider fact: missing payment, unmatched provider payment, amount/currency mismatch, fee mismatch, settlement mismatch, duplicate/out-of-order event or reversal/refund movement.

A discrepancy is review state, never silent correction.

## State contracts

Payment Intent:

draft → pending → processing → succeeded | failed | cancelled

Payment Attempt:

ready → sending → pending → succeeded | failed | expired

Settlement:

expected → reconciling → settled | discrepancy

Succeeded, failed and cancelled Payment Intent states are terminal for the intent. Refunds, reversals and chargebacks are separate append-only movements linked to the original payment.

## Non-negotiable invariants

1. Amount and currency are explicit and decimal-safe.
2. The client cannot set successful payment truth.
3. Payment success comes from an authorized application command or a verified provider event whose amount and currency exactly match the Payment Intent.
4. External payment calls happen outside the core database transaction.
5. State change and outbox publication are atomic.
6. Every critical outbound payment command is idempotent.
7. Every inbound provider event is deduplicated by immutable provider event id.
8. Payment retries reuse a stable external idempotency key.
9. Provider callbacks cannot bypass authorization, policy, audit or business invariants.
10. Settlement matching is deterministic and restartable.
11. Reconciliation discrepancies are durable review state.
12. Refunds, reversals and chargebacks are append-only adjustments.
13. Monetary calculations do not use binary floating-point.
14. Operational recovery may reclaim leases but never fabricate payment or settlement success.
15. Provider credentials, webhook secrets and signing keys are runtime secrets, never repository data.
16. A settlement statement is accepted only with an immutable statement hash.
17. A settlement cannot close while any reconciliation item remains open.

## Adapter boundary

A payment adapter may create/confirm/cancel provider payments, query provider status, verify/normalize webhooks and retrieve settlement statements.

The adapter may not write platform business tables directly, decide platform payment truth, bypass idempotency, bypass authorization/policy or rewrite economic history.

Provider SDKs and credentials stay behind the adapter boundary.

## Reconciliation

Matching priority is:

1. immutable provider payment/reference id;
2. platform payment intent id when carried by the provider;
3. exact amount + currency + statement reference;
4. controlled date window as a secondary correlation aid.

Amount-only matching is never enough to auto-close a settlement discrepancy.

Reprocessing the same provider statement must be idempotent and must not create duplicate settlement truth. A changed payload for the same provider settlement reference is treated as an integrity conflict. A discrepancy must be resolved explicitly before settlement can be closed.

## Production gate

Production Payment/Settlement is not accepted until there is evidence for:

- provider adapter contract tests;
- provider sandbox/integration tests;
- webhook signature verification;
- duplicate and out-of-order event handling;
- retry/idempotency behavior;
- timeout/network-failure recovery;
- refund/reversal/chargeback handling where supported;
- settlement statement reconciliation;
- discrepancy/review handling;
- PostgreSQL integration;
- audit/observability with redacted payment data;
- secrets/configuration checks;
- controlled release and rollback drill;
- selected production provider, merchant account, verified webhook endpoint and operational reconciliation procedure.

No production credentials or provider-specific truth is invented in the kernel repository before the provider is actually selected and configured.

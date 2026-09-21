# Production Payment & Settlement Boundary

## Purpose

This document defines the final money-execution boundary above the frozen v1.4 kernel.

v1.4 remains the stable business kernel:

Identity → Search → Intelligence → Evidence → Qualification → Commercial Action → Order → Economics → API

Payment execution and settlement are post-kernel runtime capabilities. They may depend on provider adapters, but provider behavior never becomes domain truth.

## End-to-end money flow

Order → Payment Intent → Payment Attempt → Provider Effect → Verified Provider Event → Payment State → Economic Entry → Settlement Expectation → Provider Statement → Reconciliation → Settlement Close

The flow is deliberately split into two authorities:

- PostgreSQL is authoritative for the platform's payment state and reconciliation state.
- The external payment provider is authoritative only for its own externally observed payment/settlement facts, which enter the platform through verified, idempotent adapters.

## Core records

### Payment Intent

Represents the platform's expected payment for an order.

Required facts:

- immutable order reference;
- explicit amount and currency;
- stable platform payment identifier;
- command idempotency key;
- current payment status;
- creation and update timestamps.

The client cannot directly set a successful payment state.

### Payment Attempt

Represents one concrete provider interaction.

Required facts:

- payment intent reference;
- attempt number;
- stable external idempotency key;
- worker ownership and lease while an external effect is in flight;
- provider reference when known;
- request/response timestamps;
- terminal result.

Retries are at-least-once and must not create duplicate provider charges when the provider supports idempotency.

### Verified Provider Event

Represents an inbound observation from a payment provider.

Required facts:

- immutable provider event identifier;
- provider reference;
- normalized event type;
- signature/authentication result;
- received timestamp;
- raw-provider payload reference;
- processing state.

Provider event identifiers are unique. Re-delivery of an already processed event is a no-op.

### Settlement Record

Represents provider-level movement of captured money into the merchant settlement.

Required facts:

- provider settlement identifier;
- covered payment/provider references;
- gross amount;
- fees;
- net amount;
- currency;
- settlement timestamp;
- reconciliation status.

A settlement cannot be marked closed from an operator assertion alone.

### Reconciliation Item

Represents the difference between platform expectations and provider facts.

Examples:

- expected payment missing at provider;
- provider payment has no platform reference;
- amount mismatch;
- currency mismatch;
- duplicate provider event;
- fee mismatch;
- settlement amount mismatch;
- reversed/refunded movement.

Discrepancies are durable review state. They are never silently rewritten into a matching transaction.

## State contracts

### Payment Intent

draft → pending → processing → succeeded | failed | cancelled

Succeeded, failed and cancelled are terminal for the intent itself. Refunds, reversals and chargebacks are separate append-only money movements linked to the original successful payment.

### Payment Attempt

ready → sending → pending → succeeded | failed | expired

Sending is lease-owned. An expired lease is reclaimable. Completion requires the current unexpired lease.

### Settlement

expected → reconciling → settled | discrepancy

A settled record may later receive a separate reversal/adjustment record; the original settlement fact is not mutated into another historical truth.

## Non-negotiable invariants

1. Payment amount and currency are explicit and decimal-safe.
2. Payment success is derived from an authorized application command or a verified provider event, never from client input.
3. External payment calls occur outside the core database transaction.
4. State change and outbox publication are atomic.
5. Every critical outbound payment command is idempotent.
6. Every inbound provider event is deduplicated by immutable provider event id.
7. Payment attempts use stable external idempotency keys across retries.
8. Provider callbacks cannot bypass authorization, policy, audit or business invariants.
9. Settlement matching is deterministic and repeatable.
10. A mismatch enters durable reconciliation/review state.
11. Refunds, reversals and chargebacks are append-only adjustments; the original payment fact is not overwritten.
12. Monetary calculations never use binary floating-point.
13. Audit records contain actor, correlation, provider reference, outcome and configuration version.
14. Operational repair may reclaim infrastructure leases but may never fabricate a payment or settlement success.
15. Provider credentials, webhook secrets and signing keys are runtime secrets, not repository data.

## Provider adapter boundary

The application depends on a narrow payment port.

The adapter may:

- create/confirm/cancel a provider payment;
- query provider payment status;
- verify and normalize webhook events;
- retrieve settlement statements.

The adapter may not:

- write PostgreSQL business tables directly;
- decide platform payment truth;
- bypass idempotency;
- bypass policy or authorization;
- rewrite economic history.

Concrete provider SDKs stay behind the adapter boundary.

## Reconciliation rules

Settlement reconciliation must be restartable and deterministic.

Matching priority:

1. immutable provider payment/reference id;
2. platform payment intent id when carried by the provider;
3. exact amount + currency + statement reference;
4. controlled date window only as a secondary correlation aid.

Amount-only fuzzy matching is never sufficient to auto-close a settlement discrepancy.

A reconciliation run must be idempotent: repeating the same statement cannot create duplicate settlement truth.

## Production cutover gate

Payment/settlement is not production-ready until all of the following are evidenced:

- provider adapter contract tests;
- provider sandbox/integration tests;
- verified webhook signature tests;
- duplicate and out-of-order event tests;
- retry/idempotency tests;
- timeout/network failure recovery tests;
- refund/reversal/chargeback handling tests where supported;
- settlement statement reconciliation tests;
- discrepancy/review tests;
- PostgreSQL integration tests;
- audit and observability checks with redacted payment data;
- secrets/configuration checks;
- controlled release and rollback drill;
- a selected production provider, merchant account, webhook endpoint and operational reconciliation procedure.

The repository can define and validate the provider-neutral boundary without inventing production credentials or pretending that a concrete provider is live.

# P41 — MAX Outbound Reconciliation / Idempotency Proof

P41 addresses the previously blocked MAX external-effect safety boundary without making any live MAX API call.

## Deterministic proof

The existing `MaxAdapter` is exercised through the canonical `CommunicationGateway` and `SafeCommunicationAdapter`.

The proof verifies:

- one stable idempotency key produces one external message identity;
- replaying the same request returns the same external identity;
- reusing the same idempotency key with a different request is rejected;
- different commercial actions produce distinct external identities;
- repeated delivery is deterministically deduplicated;
- a provider without proven idempotency or reconciliation is quarantined.

## Safety interpretation

This proves the platform-side idempotency behavior of the deterministic MAX adapter.

It does **not** prove that the live MAX service itself honors the same contract. Therefore no live MAX activation is enabled by P41.

A future live integration still requires provider-specific evidence that the external service preserves the required idempotency/reconciliation semantics across network failures and retries.

## Scope stop

P41 does not add:

- live MAX API traffic;
- MAX credentials;
- a new provider;
- a database migration;
- frozen-kernel changes;
- automatic adapter retries;
- production activation.

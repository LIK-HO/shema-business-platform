# P40 — Controlled AI Production Activation / Rollback Rehearsal

P40 is an operational rehearsal of the already implemented promotion and provider gates.

## Sequence

`assess_ai_promotion()`
→ explicit operator approval
→ provider remains disabled
→ explicit provider activation
→ no external provider network call
→ explicit rollback
→ provider gate disabled
→ subsequent provider invocation fails closed.

The sequence is executed independently for YandexGPT and GigaChat.

## Safety boundary

Activation is exercised with runtime-only test secrets and deterministic/no-network transports.

For GigaChat, request and token transports are replaced with a counter-based test transport. A non-zero call count would fail the rehearsal.

For YandexGPT, the existing activation implementation performs construction/readiness only; actual provider invocation remains outside the rehearsal.

## Rollback proof

After rollback:

- the activation state is disabled;
- activation and rollback telemetry are present;
- a previously returned gated provider cannot invoke the underlying adapter;
- the failure is `NOT_READY` before external provider I/O.

## What P40 does not do

P40 does not:

- enable production traffic;
- persist an approval;
- add a deployment mechanism;
- alter the HTTP contract;
- alter PostgreSQL schema;
- alter frozen kernel semantics;
- add a provider;
- add fallback routing.

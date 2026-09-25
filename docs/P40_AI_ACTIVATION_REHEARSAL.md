# P40 — Controlled AI Production Activation / Rollback Rehearsal

P40 is an evidence-only rehearsal of the operator-controlled AI promotion path.

## Rehearsal sequence

`P39 assessment`
→ explicit operator approval record
→ provider remains disabled
→ explicit YandexGPT or GigaChat activation
→ no provider network call
→ explicit rollback
→ provider disabled and configuration-gated traffic blocked.

Both approved providers are exercised independently.

## Safety boundary

The rehearsal uses deterministic requesters and never performs a live YandexGPT or GigaChat call.

Activation is not implied by the P39 approval record. Provider-specific activation gates remain the only activation mechanism.

Rollback is explicitly exercised and the post-rollback configuration gate is verified to reject future traffic.

## Scope stop

P40 does not add:

- a provider;
- an HTTP route;
- a database migration;
- frozen-kernel changes;
- automatic activation;
- Cloud ↔ Local fallback;
- live provider traffic;
- merge or deployment.

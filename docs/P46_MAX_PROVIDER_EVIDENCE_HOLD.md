# P46 — MAX Provider Evidence Hold / Revalidation

## Purpose

P46 is an evidence-only checkpoint after the P45 productization readiness audit.

The v1.5 platform-side safety controls remain verified. The only unresolved release blockers are external guarantees that belong to the MAX service itself:

1. provider-side idempotency for `POST /messages`;
2. provider-side reconciliation for an ambiguous outbound request.

P46 does not invent either guarantee and does not weaken the release gate.

## Revalidation performed

On 2026-09-25, the following authoritative MAX materials were rechecked without live API traffic:

- official `POST /messages` method documentation;
- official `GET /messages` documentation;
- official `GET /messages/{messageId}` documentation;
- official MAX API overview;
- current official OpenAPI schema snapshot `schema_2026_07_01.json`.

The current documentation confirms:

- `POST /messages` is the outbound send method;
- successful sends return a message object with a message identity;
- current documentation directs API traffic to `platform-api2.max.ru`;
- the two-messages-per-second per-destination limit remains documented;
- message retrieval by known message ID is documented.

The checked artifacts do **not** document:

- an `Idempotency-Key` header or equivalent client-supplied idempotency key for `POST /messages`;
- provider-side deduplication semantics for repeated equivalent `POST /messages` requests;
- a provider-side reconciliation contract that maps an ambiguous send to a client operation key and deterministically identifies the already-created message.

The absence is scoped to the checked authoritative artifacts. P46 does not infer an undocumented server behavior from that absence.

## Decision

The external-effect safety gate remains blocked.

No live MAX outbound activation, automatic live retry, or compensating provider/fallback is authorized by this phase.

The next revalidation should occur only when new authoritative MAX documentation/schema/API evidence changes one of the two unresolved guarantees.

## Integrity boundary

P46 changes evidence state only.

It does not:

- change production execution code;
- add a provider;
- add a retry path;
- add a reconciliation path;
- change PostgreSQL schema;
- change frozen v1.4 semantics;
- change HTTP contracts;
- enable production traffic;
- merge or deploy.

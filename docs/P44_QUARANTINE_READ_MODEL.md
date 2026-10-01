# P44 — MAX Quarantine Reconciliation Contract / Read-Only Operator Control

P44 adds a read-only platform model over the existing `quarantine_record` table.

## Purpose

The model allows a future operator experience to inspect an ambiguous commercial-action external outcome without changing business state.

Supported inspection:

- lookup by `object_type` + `object_ref`;
- optional filtering by `reason_code`;
- bounded listing of unresolved quarantine records;
- access to the already stored reconciliation payload.

## Safety boundary

The reader executes only SELECT statements.

It cannot:

- resolve or mutate a quarantine record;
- change `CommercialAction` state;
- change `FAILED` to `SENT`;
- invoke the MAX adapter;
- retry an external effect;
- add credentials or network access.

No new permission is introduced here. The future operator/experience layer must perform its own authorization before exposing this reader to a human-facing control surface.

## Reconciliation rule

An inspection result is evidence for a future explicit reconciliation decision. It is not itself a state transition.

Until provider-side MAX delivery semantics are sufficiently evidenced, the safe default remains:

`FAILED + quarantine` → inspect → explicit evidence review → no automatic resend.

P44 therefore improves operability without creating a hidden second outbound path.

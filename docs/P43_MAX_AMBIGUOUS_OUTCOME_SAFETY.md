# P43 — MAX Ambiguous External Outcome: Fail Closed

P43 closes the execution-layer gap exposed by P42.

When an external communication attempt returns an `ExternalEffectUnknown` error, the platform must not guess whether MAX accepted the message.

## Safe transition

The existing commercial action is durably moved to `FAILED`.

The same transaction also:

- records a `quarantine_record` with reason `external_effect_unknown`;
- appends an outbox event `commercial_action.external_effect_unknown`;
- appends a corresponding audit record;
- preserves the existing command idempotency reservation as `pending:<action_id>`.

The request body is not stored in the quarantine payload. The durable evidence contains request hash and stable external-effect idempotency key instead.

## Replay behavior

Because the commercial action is no longer in `READY` or `SENDING`, a later attempt cannot reclaim the action and cannot reach the communication adapter.

The adapter is therefore invoked at most once for the ambiguous command until an explicit reconciliation process changes the business state.

P43 does not attempt to infer whether the external provider actually delivered the message.

## Why this is necessary for MAX

Current official MAX materials expose message IDs and a GET-by-message capability, but do not document an idempotency key or server-side deduplication guarantee for `POST /messages`. Therefore a timeout or lost response cannot safely be converted into an automatic replay.

P43 chooses durable uncertainty over duplicate external communication.

## Scope stop

P43 does not:

- call the live MAX API;
- add MAX credentials;
- add automatic retries;
- invent provider-side reconciliation semantics;
- change the database schema;
- change the frozen kernel;
- add an HTTP route.

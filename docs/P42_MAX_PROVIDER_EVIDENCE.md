# P42 — MAX Provider-Side External-Effect Evidence

P42 records the current official MAX provider contract relevant to safe outbound activation.

## Confirmed provider facts

The current MAX developer documentation defines:

- `POST /messages` as the outbound message method;
- `Message` / `SendMessageResult` as the successful response model;
- HTTP error classes including `400`, `401`, `404`, `405`, `429`, and `503`;
- a limit of two outbound messages per second to one dialog, group chat or channel;
- Bearer-style token transmission through the `Authorization` header;
- message identity in the returned `Message.body.mid` field.

Official references:

- https://dev.max.ru/docs-api/methods/POST/messages
- https://dev.max.ru/docs-api/objects/Message
- https://dev.max.ru/docs-api
- https://github.com/max-messenger-bot/max-bot-api-schemas

## Safety finding

The reviewed official contract does **not** document an `Idempotency-Key` request field or an equivalent server-side deduplication contract for `POST /messages`.

The official OpenAPI specification describes `POST /messages` parameters and `SendMessageResult`, but no provider-side idempotency/reconciliation primitive is defined for outbound message creation.

Therefore:

- the platform-side P41 deterministic idempotency proof remains valid;
- live MAX outbound is **not** certified crash-safe by provider-side documentation;
- P41 `SafeCommunicationAdapter` must remain the production activation boundary;
- no automatic retry may be introduced for live MAX based on the current evidence;
- reconciliation would require additional provider-side evidence or a separately proven mechanism.

## Rate / retry implications

MAX documents a two-messages-per-second limit per dialog/group/channel and returns HTTP 429 when request limits are exceeded. This supports bounded rate control but does not establish safe replay after an ambiguous transport failure.

A 429/backoff policy is therefore not equivalent to an external-effect idempotency guarantee.

## Activation decision

Current evidence status:

- provider API exists: **yes**;
- authentication contract exists: **yes**;
- response identity exists: **yes**;
- rate/error semantics documented: **yes**;
- provider-side idempotency contract documented: **no evidence found**;
- provider-side reconciliation contract documented: **no evidence found**;
- live outbound activation safe for crash/retry semantics: **not certified**.

No live MAX credential or network call is introduced by P42.

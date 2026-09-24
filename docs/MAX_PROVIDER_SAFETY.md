# MAX Provider Safety Assessment

**Assessment date:** 2026-09-24

## Current published API

### Current official contract verified 2026-09-24

The current official MAX developer documentation confirms the following live contract:

- outbound messages use `POST https://platform-api2.max.ru/messages`;
- authentication is via `Authorization: <access_token>`;
- documented target parameters are `user_id` or `chat_id`;
- documented message-body fields include `text`, `attachments`, `link`, `notify` and `format`;
- the published POST `/messages` contract does not document a provider-side idempotency key or equivalent request-deduplication field;
- the successful response returns the created `message` object.

The published read surface `GET /messages` accepts `message_ids` or retrieves messages from a chat with optional time bounds and count. `GET /messages/{messageId}` requires the message ID itself. Neither published method provides a deterministic lookup by the platform's durable commercial-action idempotency key.

Source references:
- https://dev.max.ru/docs-api/methods/POST/messages
- https://dev.max.ru/docs-api/methods/GET/messages
- https://dev.max.ru/docs-api/methods/GET/messages/-messageId-

The published MAX developer contract documents outbound message creation as:

- `POST https://platform-api2.max.ru/messages`
- authentication via the `Authorization` header;
- a successful response contains the created `message` object;
- the documented request parameters do not declare an idempotency key or equivalent request-deduplication field.

Source:
https://dev.max.ru/docs-api/methods/POST/messages

MAX also publishes `GET /messages` for reading messages by `chat_id` or `message_ids`. The published contract does not define a lookup that reconciles a message by this platform's durable commercial-action idempotency key.

Source:
https://dev.max.ru/docs-api/methods/GET/messages

## Safety decision

The platform's commercial-send workflow is explicitly designed to survive a process crash after an external effect. Therefore a live provider must demonstrate at least one of:

1. provider-side idempotency keyed by the durable external-effect key; or
2. deterministic reconciliation that can prove whether that exact effect already happened before a retry.

The current published MAX contract does not provide sufficient documented evidence for either capability. This is a **capability-not-proven** decision, not a claim that MAX can never provide such a mechanism.

Accordingly, as of 2026-09-24:

```text
MAX_LIVE_EFFECT_SAFETY = {
    supports_idempotency: false,
    supports_reconciliation: false,
    activation: "fail_closed",
}
```

This is a capability-not-proven decision. It does not claim that MAX can never provide such a mechanism; it states that the current published contract does not prove the semantics required by this platform's crash-after-external-effect workflow.

The live MAX outbound adapter must not be activated.

## Enforcement

`ExternalEffectSafety` and `SafeCommunicationAdapter` form the productization gate:

- an external provider must carry an evidence reference;
- the provider is safe for crash-retry only when idempotency or reconciliation is explicitly proven;
- an uncertified provider fails closed with `QuarantineRequired` during composition;
- the frozen kernel workflow remains unchanged.

The existing `MaxAdapter` is a deterministic in-memory adapter used for tests. It is not evidence of live MAX provider semantics.

## Exit criteria for live MAX

Before live outbound activation, add a provider-specific proof covering:

- the exact external-effect key used by the workflow;
- duplicate submission behavior after a simulated process crash;
- deterministic reconciliation when the first request's response is lost;
- mismatch detection when the same key is reused with different content;
- the corresponding integration test against the real provider or an officially documented provider contract that guarantees the same semantics.

Until those conditions are proven, MAX remains inbound/read-only or test-composed from the perspective of external side effects.

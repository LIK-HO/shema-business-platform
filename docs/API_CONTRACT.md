# v1.5 Canonical API Contract

## Purpose

The HTTP API is the single application boundary for Web, PWA and Android. Clients never access PostgreSQL, repositories, adapters or provider SDKs directly.

All clients share the same command/query semantics, authorization and policy gates, idempotency rules, correlation model and error envelope.

## Request context

- Authenticated actor identity comes from the IAM boundary.
- X-Correlation-Id is propagated across the request and worker chain; the server creates one when absent.
- Idempotency-Key is mandatory for critical mutations.
- Clients cannot select business-policy versions.

## Canonical endpoints

| Endpoint | Purpose |
|---|---|
| POST /v1/ai/run | Execute one bounded AI task through the application boundary |
| POST /v1/search | Canonical company search |
| POST /v1/discovery/evaluate | Identity resolution and qualification evaluation |
| POST /v1/intelligence/research | R1-R4 policy-routed research into traceable Evidence |
| POST /v1/commercial-actions | Create gated commercial action |
| POST /v1/commercial-actions/{actionId}/send | Send READY action through its adapter |
| POST /v1/orders | Create order only from SENT or COMPLETED action |
| GET /v1/orders/{orderId} | Read canonical order state |
| GET /v1/economics/{entityRef} | Read economic lineage |
| GET /v1/diagnostics | Read operator-safe diagnostics |

## Mutation invariant

HTTP request -> command -> authorization -> policy -> idempotency -> transaction -> domain state -> outbox -> worker -> external effect -> audit

External effects are never executed by the client and never inside the core database transaction.

## Error model

Every application error returns code, message, correlationId and optional safe details.

HTTP mapping: 400 malformed request; 401 unauthenticated; 403 authorization/policy denial; 404 unknown resource; 409 idempotency/state conflict; 422 validation failure; 423 quarantined/review-required; 429 budget/rate limit; 500 unexpected internal error; 503 temporary dependency failure.

## Client boundary

Web, PWA and Android use versioned DTOs and canonical application semantics. They may cache projections and drafts locally, but identity, evidence, qualification, commercial action, order and economic state remain authoritative on the server.

## AI execution boundary

POST /v1/ai/run is an experience-layer route only.

The HTTP request may provide task metadata, evidence references and explicit request budgets. It cannot provide provider selection, model identity, actor trust, resource trust or evidence-trust levels, production activation state, or provider credentials.

The route delegates execution to the APIApplication boundary. The application layer remains responsible for constructing the frozen AIGateway inputs, resolving trusted resource/evidence state, applying authorization and policy, invoking the already-composed provider boundary, and persisting the canonical AIRun.

Production YandexGPT traffic remains subject to the separate P28 production activation gate. No provider is implicitly activated by exposing this route.

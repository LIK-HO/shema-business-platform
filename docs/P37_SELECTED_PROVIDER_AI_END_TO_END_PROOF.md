# P37 — Selected Provider End-to-End HTTP Proof

P37 proves the complete canonical AI request path after the operator-level provider selection introduced by P36.

## Verified path

`POST /v1/ai/run`
→ `ApprovedAIRuntimeAssembly`
→ `AIOnlyAPIApplication`
→ `AIExecutionService`
→ frozen `AIGateway`
→ selected YandexGPT or GigaChat composition
→ PostgreSQL `ai_run` and audit record.

## Provider proof

Both approved cloud providers are exercised with deterministic test-only transports:

- YandexGPT-selected runtime;
- GigaChat-selected runtime.

The deterministic transports preserve the existing provider contracts but make no external network calls.

## Failure proof

The integration proof also verifies:

- an inactive selected provider fails closed;
- expired evidence fails closed before provider invocation;
- the unselected provider receives no invocation;
- correlation identifiers reach the canonical response and persistence path.

## Scope stop

P37 does not add:

- a new provider;
- provider selection in the HTTP request;
- automatic fallback;
- local/self-hosted runtime;
- database schema or migration;
- frozen kernel changes;
- automatic production activation;
- live provider traffic.

This is an executable evidence phase for the already composed productization path.

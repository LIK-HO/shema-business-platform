# AI Provider Composition / Activation Proof

## Purpose

P27 composes the verified YandexGPT adapter with the frozen v1.4 AI Gateway without modifying `application/ai.py` or changing Gateway semantics.

## Why a composition bridge exists

The frozen `AIGateway.execute()` passes only `AITask` and `input_refs` into the frozen `AIProvider.run()` contract. P25 adapters additionally require evidence references, execution context, budget and a bounded deadline.

The bridge therefore uses a request-scoped `ContextVar` created only by `execute_scoped_ai()` / `bind_ai_execution_scope()`. The scope is immutable and is always reset with the context token in `finally`.

## Execution sequence

`execute_scoped_ai → bind scope → frozen AIGateway.authorization/policy/evidence → ScopedAIProvider → readiness/activation → P25 request → concrete provider adapter → P25 response validation → frozen AIGateway budget validation → PostgreSQL/audit`

The external provider call remains outside the database transaction because that property belongs to the frozen Gateway.

## Fail-closed rules

- no correlation ID: reject before scope binding;
- provider invocation without an active scope: reject before adapter I/O;
- disabled or non-explicit provider activation: reject;
- non-ready provider: reject;
- adapter response is revalidated at the composition boundary;
- unexpected adapter exceptions become typed non-retryable composition failures;
- no cloud/local automatic fallback;
- telemetry is non-authoritative and cannot break the request path.

## Concurrency / scope safety

The scope is a frozen dataclass stored in `contextvars.ContextVar`, not a mutable process-global object. Tests cover nested reset and independent thread contexts.

## Persistence and truth

`ScopedAIProvider` does not persist anything. Canonical `AIRun` and audit persistence remain exclusively inside the frozen `AIGateway` UoW after provider execution.

## Production activation

This PR proves composition. It does not wire YandexGPT traffic into `experience/api.py` or another production route automatically. Production activation remains an explicit runtime composition decision after this proof is verified.

## Scope stop

Not included:

- modifications to frozen `src/shema_platform/application/ai.py`;
- second provider implementation;
- local model runtime;
- cloud/local fallback;
- provider-owned canonical persistence;
- production traffic activation;
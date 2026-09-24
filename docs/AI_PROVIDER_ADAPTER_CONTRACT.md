# AI Provider Adapter Contract

## Purpose

P25 defines the provider-neutral adapter boundary outside the frozen v1.4 kernel.

The contract is deliberately one level below concrete integrations. It does not implement YandexGPT, GigaChat or a local model runtime. It defines the invariants every future adapter must satisfy before P26 can activate a concrete provider.

## Boundary

The frozen `shema_platform.application.ai.AIGateway` remains unchanged.

Concrete adapters live under `src/shema_platform/adapters/ai/` and cannot become a source of canonical business truth. PostgreSQL remains the only canonical transactional authority.

### Approved provider classes

Cloud provider identifiers are limited to:

- `yandexgpt`
- `gigachat`

Local/self-hosted models are permitted only after the model license has been verified to allow free commercial use for the intended scenario.

No other cloud provider can enter this boundary without an explicit manifest/architecture change.

## Adapter descriptor

Every adapter exposes a descriptor containing:

- provider and model identity/version;
- configuration version;
- declared capabilities;
- bounded resource limits;
- model provenance.

For local/self-hosted models, provenance must include source, license, license URL, license verification date, artifact/model digest, runtime and security status, plus an explicit `free_commercial_use_verified` flag.

## Activation and readiness

Activation is explicit and versioned.

A provider is not considered usable merely because a class exists or credentials exist. Future composition must satisfy:

`descriptor → explicit activation → readiness → invoke`

Readiness is operational state only. It must not contain secrets or raw provider payloads.

An unconfigured, unhealthy or security-blocked provider fails closed.

## Invocation contract

A future adapter invocation receives:

- operation identity;
- the frozen `AITask` contract;
- input references;
- evidence references;
- execution context/correlation;
- AI budget;
- bounded deadline.

The adapter returns a structured response containing:

- the existing `AIRun` domain result;
- configuration version;
- provenance reference;
- provider request identity when the provider exposes one;
- timestamp.

Raw provider response bodies are not part of the adapter response contract.

## Mandatory response validation

Before the response is accepted:

- provider ID must match the descriptor;
- task ID and prompt version must match the request;
- input references must match exactly;
- returned evidence references must be a subset of request evidence;
- configuration version must match;
- token/cost/duration limits must remain inside both operation and adapter budgets.

## Failure and retry semantics

Failures use a bounded typed taxonomy: configuration, readiness, authentication/authorization, license, model availability, rate limit, resource exhaustion, deadline, transport, invalid response, policy and security blocks.

Provider-specific retries are denied by default. A retry is permitted only when the adapter supplies explicit retry-safety evidence.

There is no implicit Cloud→Local or Local→Cloud fallback.

## Scope stop

P25 does **not**:

- implement a concrete cloud provider;
- install a local model runtime;
- change the frozen AI Gateway;
- add a new provider;
- add provider-owned persistence;
- introduce automatic fallback routing.

P26 is the next bounded boundary: one concrete approved provider implementation at a time, with current external contract evidence and its own activation, resource, security, observability and recovery proof.

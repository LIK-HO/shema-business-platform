# AI Provider Adapter Contract

## Purpose

P25 defines the single provider-neutral adapter boundary used by the frozen AI Gateway.

The contract supports two provider classes:

- approved cloud providers governed by `architecture/ai_provider_policy.json`;
- local/self-hosted LLMs whose license has been verified as permitting free commercial use for the intended scenario.

No concrete provider or model is implemented by this boundary.

## Adapter interface

`shema_platform.application.ai_provider.AIProviderAdapter` exposes exactly three operations:

1. `describe()` — returns an immutable provider/model/configuration snapshot;
2. `readiness()` — reports explicit readiness or a fail-closed reason;
3. `execute(request)` — performs one bounded provider operation.

The adapter receives no `UnitOfWork`, repository, canonical entity, order, commercial action or other persistence handle.

## Provider snapshot

The descriptor records:

- provider identity and class;
- model and model version;
- configuration version;
- capabilities;
- operational limits;
- provenance and security status.

For local/self-hosted models the descriptor additionally requires:

- license name and URL;
- license verification date;
- model artifact digest;
- runtime;
- verified free-commercial-use permission.

Credentials are intentionally absent from the descriptor because credentials are runtime-only.

## Execution envelope

`AIProviderRequest` carries the task, input references, evidence references, application execution context, budget and the exact provider descriptor snapshot selected for the operation.

This prevents an adapter from silently changing provider/model/configuration between selection and execution.

The gateway remains responsible for:

- authorization;
- policy evaluation;
- evidence requirement;
- budget enforcement;
- provider/model/configuration consistency;
- persistence and audit.

## Readiness and failures

A provider is either `ready`, `not_ready` or `disabled`.

Non-ready states require an explicit reason and cause the gateway to fail closed.

Adapter failures use a typed failure taxonomy. The adapter contract intentionally has no retry API and no automatic fallback. Any future retry must be justified by the enclosing workflow's idempotency and external-effect semantics, not invented inside a provider adapter.

## Response validation

The gateway validates that the returned `AIRun` matches the selected descriptor and request:

- provider ID;
- model;
- model version;
- task ID;
- prompt version;
- input references;
- evidence references;
- token, cost and duration budgets;
- adapter duration limit.

Provider output is therefore treated as untrusted external data, not canonical business truth.

## Audit and observability

Successful execution records the selected provider class, model/configuration version, capabilities and security status in audit metadata.

No credentials, authorization headers or raw provider payload are introduced by this contract.

Provider selection is therefore reproducible and observable without turning provider metadata into a second system of record.

## Explicit non-goals

P25 does not:

- implement YandexGPT;
- implement GigaChat;
- install a local model runtime;
- add another cloud provider;
- add automatic cloud/local fallback;
- change the frozen kernel;
- grant AI authority over canonical business state.

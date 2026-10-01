# P30 — Concrete YandexGPT Application Composition

P30 closes the application-side gap between the canonical AI HTTP route and the already verified YandexGPT adapter/composition/production gate.

## Boundary

The execution path is:

HTTP `POST /v1/ai/run`
→ `AIOnlyAPIApplication`
→ provider-neutral `AIExecutionService`
→ frozen `AIGateway`
→ P27 scoped composition
→ P28 YandexGPT production gate
→ YandexGPT adapter.

The HTTP layer still does not select providers, assert trust levels, supply credentials or persist AI results.

## Trust resolution

The application does not trust client-supplied resource/evidence trust.

`PostgresAIExecutionTrustResolver` reads canonical PostgreSQL state:

- identity state derives resource trust;
- supplied evidence references must exist;
- evidence must belong to the requested resource;
- evidence must be active and unexpired;
- T0..T4 are mapped to bounded numeric evidence levels;
- missing, unrelated, invalid or unusable evidence fails closed to quarantine.

This resolver is read-only and does not become a second source of truth.

## Gateway ownership

The application service constructs the frozen `AIGateway` per request with the authenticated actor's verified permission set.

The Gateway remains responsible for:

- authorization;
- policy;
- evidence requirement;
- provider-result validation;
- budget enforcement;
- canonical AI-run persistence;
- audit.

The external provider call remains outside the Unit of Work.

## Activation

YandexGPT remains disabled until an explicit operator activation through `YandexGPTProductionGate`.

No startup path automatically activates production traffic.

Rollback disables subsequent requests and leaves canonical business state unchanged.

## Provider policy

- Cloud AI: YandexGPT and GigaChat only.
- Local/self-hosted LLM: only with verified free commercial-use rights and required provenance metadata.
- No implicit cloud/local fallback.
- OpenAI is not an approved provider for this platform.
- P30 does not implement GigaChat or a local runtime.

## Scope stop

P30 does not modify frozen kernel semantics, database schema/migrations, canonical persistence ownership or provider allow-list semantics.

A provider adapter is never a system of record.

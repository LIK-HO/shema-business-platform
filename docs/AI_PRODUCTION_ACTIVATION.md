# AI Production Activation

P28 defines the reversible production activation boundary for the already verified YandexGPT adapter and P27 composition.

## Activation prerequisites

Production traffic is denied unless all conditions hold:

1. the configuration snapshot environment is exactly `production`;
2. feature flag `ai.yandexgpt.production.enabled` is explicitly enabled;
3. an operator identity is supplied to the activation call;
4. `YANDEXGPT_API_KEY` exists only at runtime and is not stored in the snapshot;
5. all required YandexGPT operational values are present in the immutable configuration snapshot;
6. the provider reports `ready`;
7. telemetry is supplied;
8. provider cost and duration ceilings are bounded by the activation snapshot.

The gate does not activate anything automatically during application startup.

## Runtime enforcement

A gated provider checks on every request that:

- the active configuration version matches the request correlation context;
- the request cost does not exceed the production activation cost ceiling;
- the request deadline does not exceed the production activation duration ceiling;
- the existing P27 composition boundary remains in force.

The frozen `AIGateway` continues to own canonical AI-run persistence and audit.

## Rollback

Rollback is explicit and operator-controlled. It:

- disables the gate immediately for subsequent requests;
- records the configuration version being rolled back;
- records operator and reason;
- emits non-authoritative telemetry;
- leaves canonical business state untouched.

A new process starts with the gate disabled. Re-activation requires a fresh explicit activation operation against the desired configuration snapshot.

## Scope exclusions

P28 does not:

- change `application.ai`;
- change the frozen kernel;
- change the database schema or migrations;
- add GigaChat implementation;
- add a local/self-hosted runtime;
- introduce cloud/local fallback;
- wire a production HTTP route automatically;
- grant provider adapters canonical business authority.

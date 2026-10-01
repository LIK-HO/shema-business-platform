# P32 — End-to-End AI Execution Proof

P32 proves the assembled AI path without introducing a new production provider or requiring live cloud traffic in CI.

## Verified path

HTTP POST /v1/ai/run
→ canonical APIApplication
→ AIExecutionService
→ frozen AIGateway
→ P27 scoped composition
→ P28 production gate
→ deterministic test transport implementing the existing YandexGPT provider contract
→ PostgreSQL AIRun + audit persistence.

## Proofs

The integration proof verifies:

- production activation remains explicit;
- provider construction does not occur before activation;
- canonical identity/evidence trust is resolved from PostgreSQL;
- active evidence permits execution;
- the same correlation ID reaches the HTTP response, AIRun workflow and audit row;
- canonical AIRun and audit records are durably persisted;
- expired evidence returns HTTP 423;
- an invalid evidence state prevents provider invocation.

The test transport is test-only. It does not alter the production YandexGPT adapter, provider allow-list or deployment behavior.

## Stop line

P32 is a composition/reliability proof. It is not authorization to enable live YandexGPT traffic and does not introduce OpenAI, GigaChat implementation, local runtime or cloud/local fallback.

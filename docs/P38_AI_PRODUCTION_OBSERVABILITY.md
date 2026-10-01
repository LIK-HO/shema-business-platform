# P38 — AI Production Observability Contract

P38 formalizes the operational telemetry already used by the AI execution path.

## Event families

The contract covers four existing event families:

- `ai.production.activated`;
- `ai.production.rolled_back`;
- `ai.provider.completed`;
- `ai.provider.failed`.

## Safe operational metadata

Provider execution events may expose the provider and immutable configuration version. Activation and rollback events may additionally expose the explicit operator identifier.

All telemetry passes through the existing allowlist and string-length limits.

## Redaction boundary

Telemetry must not contain credentials, authorization headers, prompts, input references, evidence references, provider outputs or model inputs.

The telemetry sink is non-authoritative. A logging or telemetry backend failure must never break the business execution path.

## Scope

P38 does not introduce a telemetry backend, provider, route, migration or alternate AI execution path. Production activation remains explicit and provider-specific.

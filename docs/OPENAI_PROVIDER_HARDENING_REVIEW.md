# P25 — OpenAI Provider Hardening Review

## Review date
2026-09-24

## Review boundary
Re-audit the closed P24 OpenAI provider against the frozen core, the AI Gateway authorization/policy/evidence/budget boundary, provider activation/readiness/resource/cost controls, failure/retry/response-integrity behavior, security, the current OpenAI public contract, and the bounded-complexity rule.

## Findings

### Provider contract
The current OpenAI public contract confirms the P24 assumptions: Responses supports max_output_tokens; store is explicit and P24 sends store=false; Responses expose output items, status, model, id and usage; GET /models/{model} is the documented model retrieval surface; GPT-6 Luna is currently published as gpt-6-luna at the reviewed standard short-context rate of $0.10 per 1M input tokens and $0.50 per 1M output tokens.

### Security and activation
Verified: explicit feature-flag activation; runtime-only API secret; secret excluded from versioned configuration; exact HTTPS origin; redirect rejection; no provider tools; no response storage; no automatic provider retry. No additional provider-local security control with non-redundant production risk reduction was identified.

### Resource and cost safety
Verified: bounded input; bounded serialized request body; bounded response body before JSON materialization; bounded extracted output; bounded output-token request; execution timeout; process-local rate guard; preflight cost ceiling; post-response cost ceiling using the configured pricing snapshot. The preflight estimate is an operational guard, not billing truth. No additional local limiter, billing ledger or retry scheduler is justified by current evidence.

### AI Gateway boundary
The existing gateway already enforces permission before provider execution, policy before provider execution, evidence requirements, provider/task/prompt/input-reference consistency, provider evidence subset of caller-supplied evidence, token/cost/duration budgets, and persistence/audit only after the external provider call. The provider call remains outside the Unit of Work.

### Failure and recovery
P24 performs no automatic provider retry. Paid inference is not assumed idempotent, so timeout/lost-response paths are not silently multiplied. The adapter does not invent a response store or reconciliation protocol; a higher-level durable workflow must decide whether repeated inference is acceptable. Adding provider-specific retry/reconciliation here would exceed the element boundary.

### Observability
The platform already provides correlated HTTP telemetry and durable successful ai.run audit records through the existing application boundary. P25 found no evidence requiring a provider-specific telemetry contract before workflow integration. A later workflow may add an explicit operation-level observation boundary if production evidence shows outer-layer diagnostics are insufficient.

### Frozen-core semantics
No frozen-core change is justified. P24 remains outside the domain/kernel, writes no canonical business truth directly, adds no migration and introduces no new system-of-record dependency.

## Decision
P25 CLOSED / VERIFIED — NO ADDITIONAL OPENAI PROVIDER-HARDENING CODE REQUIRED.

The P24 provider boundary is sufficiently bounded for the current productization stage. Further micro-hardening without new measured risk would violate the bounded-complexity direction.

## Next bounded productization boundary
P26 — AI WORKFLOW INTEGRATION PROOF.

Scope: one real application workflow using the existing AIGateway and verified OpenAI adapter, with explicit authorization/policy/evidence/budget semantics and durable ai_run persistence. No domain semantic change, no AI ownership of business truth, and no automatic provider retry semantics.
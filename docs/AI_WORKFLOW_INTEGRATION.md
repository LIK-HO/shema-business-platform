# P26 — AI Workflow Integration Proof

P26 proves one complete application path without enabling live paid inference:

OpenAI provider adapter -> AIGateway -> canonical PostgreSQL ai_run + audit_log.

The provider transport is replaced only at the HTTP requester seam with a deterministic response fixture. The workflow therefore exercises the real provider adapter parsing, cost calculation, evidence-reference construction, the real AIGateway authorization/policy/budget checks, and the real PostgreSQL persistence boundary without requiring an API key or creating an external provider effect.

Verified invariants:

- authorization is evaluated before provider execution;
- required evidence is present and provider evidence remains within the caller-supplied evidence set;
- provider call is outside the Unit of Work;
- the resulting AIRun is durably stored in PostgreSQL;
- the successful ai.run audit record carries the workflow correlation id;
- no OpenAI SDK, migration or canonical business-state mutation is introduced;
- CI must never perform live paid inference.

This is a composition proof, not a production activation or external-provider end-to-end test.

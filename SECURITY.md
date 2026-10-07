# Security Standard — Global Adversarial Baseline

## Status

This repository does **not** claim immunity or literal immortality.

The security objective is survivability under hostile input, compromised dependencies, provider failure, operator error, concurrency, partial deployment, ambiguous external outcomes and recovery events.

A control is not considered proven because a document, contract or positive-path test says that it exists. A security boundary is proven only when the runtime enforces it and an adversarial/negative test demonstrates that bypass fails on the current HEAD.

## Trust model

The system uses zero-trust assumptions: authentication and authorization are separate decisions, and network position or possession of an object identifier never creates implicit authority. This follows the core principle of NIST Zero Trust Architecture and OWASP API guidance on object- and function-level authorization.

Critical transitions are mediated in this order:

`untrusted input → authenticated actor/edge identity → explicit permission → resource scope → validated data → evidence provenance → policy → state invariant → transaction/concurrency → external-effect reservation → external call → reconciliation → audit → recovery`

Breaking any mandatory transition blocks the operation or sends it to quarantine/reconciliation.

## Non-negotiable invariants

1. **Server authority**
   Client-supplied permissions, ownership, provenance, correlation identifiers, provider confidence, timestamps, URLs and security decisions are data, not authority.

2. **Object-level authorization**
   A valid permission never implies access to every object. Object ownership/scope is checked server-side for sensitive resources.

3. **Evidence provenance**
   A caller cannot manufacture authoritative evidence by submitting fields that resemble an official observation. Authoritative evidence must come from a server-controlled provider boundary.

4. **Canonical state**
   PostgreSQL/canonical repositories remain the source of truth for durable business state. Projections, caches and UI state never become a second authority.

5. **External-effect safety**
   Critical external effects require durable idempotency reservation before the effect. Unknown outcomes stop retries until reconciled.

6. **Public-edge isolation**
   Public intake is untrusted. Browser-controlled headers cannot define rate-limit identity or bypass bot verification. The public path cannot create live Bitrix transactions directly.

7. **Resource exhaustion bounds**
   Body size, provider calls, AI calls, queue depth, retries, response sizes and execution time are bounded. A provider outage must not become an unbounded retry amplifier.

8. **Outbound destination integrity**
   Sensitive outbound integrations use pinned destinations and do not automatically follow redirects across trust boundaries.

9. **Fail closed**
   Missing verifier, missing allowlist, missing capability, unknown provider identity, stale evidence, missing owner scope or ambiguous external result causes rejection/quarantine/reconciliation, not best-effort continuation.

10. **Audit integrity**
    Correlation is server-generated. Audit records retain actor, action, resource, outcome and configuration lineage without accepting caller-controlled forensic authority.

11. **Frozen-kernel integrity**
    Security hardening must not silently modify frozen kernel semantics. Kernel integrity checks remain an independent release gate.

12. **Recovery**
    Restore/replay paths must be idempotent, lease-safe and auditable. A recovered database must not create duplicate projections or external effects.

## Adversarial test classes

Every material change is tested against:

- authenticated-but-unauthorized requests;
- foreign-object identifier substitution (BOLA/IDOR);
- client-supplied evidence/provenance substitution;
- replay and same-key/different-payload conflicts;
- concurrent identical requests;
- provider outage, timeout, rate limit and stale data;
- outbound redirect/SSRF substitution;
- prompt injection and untrusted AI output handling;
- body/queue/provider-budget exhaustion;
- partial transaction and crash windows;
- recovery/replay and duplicate-worker races;
- unsafe runtime composition;
- dependency/action supply-chain drift.

## External security references

The threat model is aligned to the current OWASP API Security Top 10, OWASP Top 10 for LLM/GenAI Applications 2025, NIST Zero Trust Architecture, and GitHub's current Actions supply-chain guidance.

References:
- OWASP API Security Project: https://owasp.org/projects/api-security-project
- OWASP API1 Broken Object Level Authorization: https://api-security.owasp.org/editions/2023/en/0xa1-broken-object-level-authorization/
- OWASP API4 Unrestricted Resource Consumption: https://api-security.owasp.org/editions/2023/en/0xa4-unrestricted-resource-consumption/
- OWASP GenAI Top 10 2025: https://genai.owasp.org/llm-top-10/
- NIST Zero Trust Architecture: https://www.nist.gov/publications/zero-trust-architecture
- GitHub Actions security: https://docs.github.com/en/actions/how-tos/secure-your-work
- GitHub secure-use reference: https://docs.github.com/en/actions/reference/security/secure-use

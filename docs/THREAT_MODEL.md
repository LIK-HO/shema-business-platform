# Threat Model — Global Adversarial Re-baseline

## Security boundary

The attacker is assumed to know the public API, inspect JavaScript/network traffic, replay requests, replace object identifiers, submit arbitrary Unicode/text, rotate public client identifiers, send malformed JWTs, trigger provider failures, race concurrent requests and exploit dependency/runtime configuration.

A trusted actor is not trusted with arbitrary object access. A valid credential proves identity; the application must still prove capability and resource scope.

## Primary attacker paths

### A. API authorization

Attack:
`valid token + valid role + foreign object ID`

Required result:
`403/423/404 according to resource policy; no state mutation; no external effect; audit event`.

### B. Evidence forgery

Attack:
submit `canonical_name`, `legal_status`, `claim_confidence`, `observed_at` and an official-looking URL as if they were an official registry observation.

Required result:
client fields are rejected or treated only as untrusted request data. Authoritative Evidence can only be created by the server/provider boundary.

### C. Public intake abuse

Attack:
rotate `X-Public-Client-Key`, spoof bot headers, omit Origin, send oversized bodies, enumerate identifiers, replay idempotency keys, or create provider amplification.

Required result:
rate limits derive from trusted edge identity, bot verification is server-side, body size is bounded, lookup budgets are bounded and missing security prerequisites fail closed.

### D. External request pivot

Attack:
replace an integration URL with an attacker HTTPS host or use a 30x redirect to a private address.

Required result:
destination allowlist rejects the configuration and the HTTP transport does not automatically follow redirects.

### E. AI replay and prompt injection

Attack:
inject instructions through client text/evidence, force unsafe tool/output interpretation, or replay the same expensive request after an ambiguous provider outcome.

Required result:
untrusted content stays data, downstream action authorization is independent of model output, the AI command requires durable idempotency, and an unresolved reservation blocks blind retry.

### F. Concurrency

Attack:
race two operators or workers against the same commercial action, order, repeat plan, outbox event or idempotency key.

Required result:
server-side ownership/lease/revision/unique constraints serialize or reject the conflict.

### G. Recovery

Attack/failure:
crash after external success but before local completion; restore database; replay outbox; start duplicate workers.

Required result:
canonical state remains reconstructable and replay is duplicate-safe. Unknown external outcome enters reconciliation rather than automatic retry.

### H. Supply chain

Attack:
mutable GitHub Action tag, compromised dependency, malicious artifact or changed workflow behavior.

Required result:
actions are pinned to immutable commit SHAs, dependency vulnerability checks run in CI, and release artifacts can be tied to build provenance/attestation before production use.

## Severity disposition

**P0:** bypass permits unauthorized external effect, canonical corruption, credential compromise, or unrecoverable split-brain.

**P1:** exploitable authorization/evidence/resource/recovery weakness with bounded but material impact.

**P2:** defense-in-depth weakness with a defined compensating control and owner.

No severity is considered closed merely because a document describes a control. Closure requires runtime enforcement plus executable evidence on the current HEAD.

## Known hardening already established in the re-baseline

- explicit authorization permissions for sensitive API capabilities;
- server-generated correlation IDs;
- server-authoritative counterparty evidence boundary;
- trusted peer identity for public rate limiting;
- hard HTTP body limit;
- server-side bot-verification boundary;
- pinned outbound provider destinations;
- redirect-free outbound HTTP transport;
- versioned/authority-qualified public preflight cache keys;
- lease-safe public intake outbox;
- durable idempotency for public intake and AI execution;
- resource owner fields for commercial actions, orders and repeat-order plans;
- foreign-owner negative tests;
- provider activation confirmation separated from permission;
- public readiness response reduced to a minimal health signal;
- CI actions pinned to commit SHA;
- frozen AI kernel integrity restored and independently guarded.

## Not yet a release claim

The presence of the controls above does not mean the system has passed the complete survivability gate. The current HEAD must still pass the full quality, integration, recovery and release-contract matrix before a release state is allowed.

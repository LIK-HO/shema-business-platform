# Security Evidence Matrix — v1.5 Global Re-baseline

This document is an evidence index, not a certification claim.

A control is considered closed only when:
1. the runtime enforces it;
2. an adversarial/negative test demonstrates the boundary;
3. the test passes on the current HEAD; and
4. the full release gate passes after the change.

| Boundary | Runtime enforcement | Adversarial evidence | Current closure rule |
|---|---|---|---|
| Authentication | OIDC issuer/audience/expiry/sub + algorithm allowlist | JWT negative tests | current-head CI required |
| Function authorization | explicit Permission checks | authenticated-but-no-permission API tests | current-head CI required |
| Object authorization | owner scope on sensitive resources | foreign-owner/BOLA tests | current-head CI + persistence tests |
| Evidence provenance | server-side authoritative provider boundary | client-evidence rejection tests | current-head CI required |
| Public identity | trusted peer identity | rotating client-key attack test | current-head CI required |
| Bot protection | server-side verifier boundary | spoofed-header test | insecure composition must fail |
| Resource bounds | HTTP body/provider/AI/queue limits | oversized/retry/resource tests | current-head CI required |
| SSRF | pinned integration hosts + no redirect following | attacker-host/redirect tests | current-head CI required |
| Idempotency | durable reservation before critical effect | replay/conflict/race tests | current-head CI + recovery |
| Outbox | database lease + replay | concurrent-claim/replay tests | integration + recovery |
| AI execution | provider activation, trust resolution, durable idempotency | AI replay and negative-path tests | current-head CI + release gate |
| Audit/forensics | server correlation + append-only audit | correlation spoof tests | current-head CI required |
| Frozen kernel | independent integrity gate | kernel drift test | promotion blocked on mismatch |
| CI supply chain | immutable action SHAs + dependency audit | CI supply-chain job | full release gate |
| Recovery | backup/PITR + replay-safe workers | restore/replay drill | backup-recovery gate |

## Control names retained for compatibility
Fail-closed / failure behavior; Executable evidence; Release gate.


The following labels are retained only as evidence-matrix identifiers for existing
maturity tests and release documentation. They do not constitute certification:
OIDC issuer HTTPS; OIDC JWKS HTTPS; Explicit asymmetric JWT algorithms;
Permission materialization; Production docs disabled; Telemetry allow-list redaction;
Authorization headers excluded from telemetry; Dependency vulnerability gate;
Production PITR recovery.

## Explicit non-claims

This matrix does not claim zero vulnerabilities, exploit-proof software, or literal immortality. It records security invariants and the evidence required to close them.

See SECURITY.md, docs/THREAT_MODEL.md, architecture/security_invariants_contract.json, and architecture/global_adversarial_survivability_gate_contract.json.

# Security Evidence Matrix — v1.5 Global Re-baseline

This document is an evidence index, not a certification claim.

A control is considered closed only when:
1. the runtime enforces it;
2. an adversarial/negative test demonstrates the boundary;
3. the test passes on the current HEAD; and
4. the full release gate passes after the change.

**Current security re-baseline evidence:** Phase 3C-2 exact implementation HEAD passed full seven-job release-gate CI #2073 (`36577339818`): quality 3.12/3.13, supply-chain, integration 3.12/3.13, backup/recovery and release-contract. This is current implementation-head evidence for the security boundaries recorded below; it does not claim zero vulnerabilities outside the reviewed scope.

| Boundary | Runtime enforcement | Adversarial evidence | Current closure rule |
|---|---|---|---|
| Authentication | OIDC issuer/audience/expiry/sub + algorithm allowlist | JWT negative tests | current-head CI required |
| Function authorization | explicit Permission checks | authenticated-but-no-permission API tests | current-head CI required |
| Permission non-escalation | explicit Permission membership; no wildcard/derived capability | permission-combination negative matrix + unknown-permission rejection | current-head CI required |
| Object authorization | canonical owner scope on sensitive resources and resource reads | foreign-owner/BOLA tests, resource-read API negatives and persistence tests | current-head CI + persistence tests |
| Counterparty monitoring/favorites scope | separate monitoring/favorite permissions; actor-scoped persistence and service reads | missing-permission, cross-actor, duplicate-command and snapshot-tamper negative tests | current-head CI + integration |
| Counterparty monitoring checkpoint/recovery | durable daily batch/item checkpoints; lease ownership CAS/reclaim; bounded attempts/backoff; fail-closed provider/snapshot handling | outage-without-change, duplicate replay, stale-worker reclaim, max-attempt provider suppression and PostgreSQL recovery tests | current-head CI #2073 + integration + backup/PITR |
| Evidence provenance | server-side authoritative provider boundary | client-evidence rejection tests | current-head CI required |
| Public identity | trusted peer identity | rotating client-key attack test | current-head CI required |
| Bot protection | server-side verifier boundary | spoofed-header test | insecure composition must fail |
| Resource bounds | HTTP body/provider/AI/queue limits | oversized/retry/resource tests | current-head CI required |
| SSRF | pinned integration hosts + no redirect following | attacker-host/redirect tests | current-head CI required |
| Idempotency | durable reservation before critical effect | replay/conflict/race tests | current-head CI + recovery |
| External-effect lease ownership | atomic worker+lease guard for UNKNOWN outcome transition | stale-worker/reclaimed-lease negative test + PostgreSQL persistence test | current-head CI + integration/recovery |
| Public-intake outbox lease ownership | publication requires current worker lease after reclaim protection | stale-worker/reclaimed-event PostgreSQL negative test | current-head CI + integration |
| Provider activation rollback CAS | rollback requires the currently active activation version and timestamp | stale-rollback after reactivation unit + PostgreSQL persistence test | current-head CI + integration |
| Stale provider binding | provider instances require exact activation version and timestamp; stale caches are rejected | YandexGPT/GigaChat/DaData reactivation negative tests | current-head CI + unit |
| Stale local activation state | canonical rollback clears the authoritative gate even when a replica cache remains enabled | YandexGPT/GigaChat remote-rollback reactivation negative tests | current-head CI + unit |
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

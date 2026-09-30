| Phase 4 global acceptance | public/operator surfaces, browser security headers, protected API fail-closed boundary, no client-side business state, same-origin API binding | `tests/test_phase4_global_acceptance.py` + full seven-job release gate `36588002294` on runtime HEAD `13de9b974bf59070dfbe2f4cd69f5ec7255c42f4` | CLOSED / VERIFIED |
# Security Evidence Matrix — v1.5 Global Re-baseline

This document is an evidence index, not a certification claim.

A control is considered closed only when:
1. the runtime enforces it;
2. an adversarial/negative test demonstrates the boundary;
3. the test passes on the current HEAD; and
4. the full release gate passes after the change.

**Current security re-baseline evidence:** Phase 4 final runtime HEAD `13de9b974bf59070dfbe2f4cd69f5ec7255c42f4` passed full seven-job release-gate CI `36588002294`: quality 3.12/3.13, supply-chain, integration 3.12/3.13, backup/recovery and release-contract. This is implementation-head evidence for the reviewed Web/operator boundaries; it does not claim zero vulnerabilities outside the reviewed scope.

| Boundary | Runtime enforcement | Adversarial evidence | Current closure rule |
|---|---|---|---|
| PWA offline/cache trust boundary | service worker caches public shell/assets only; `/v1/*` and protected business state stay network-only; pending mutations are bounded, memory-only and idempotent | `tests/test_phase5_pwa_acceptance.py` + HTTP bootstrap regression + full current-head release gate `36635383440` on HEAD `337b3c3f8465b406d13f6655f8e65910efe4524a` | CLOSED / VERIFIED |
| Phase 7B cloud foundation boundary | production edge/runtime/storage/secret roles are explicit; PostgreSQL remains transactional authority; image digest pinning and Lockbox injection are required; Message Queue is non-authoritative | `tests/test_phase7_yandex_cloud_foundation_acceptance.py` + SI-28 + CI `36703937084` 7/7 GREEN + Terraform validation `36703936845` GREEN on HEAD `4f2589610a9c8c8839c174c6c9b7e5873dae84ef` | CLOSED / VERIFIED |
| Phase 7 overall | live Yandex resource provisioning, database/secret/observability/backup/rollback evidence and final production smoke | Phase 7C live environment evidence required | IN_PROGRESS |
| Phase 7C live provisioning boundary | manual protected apply, live resource evidence, same-VPC database evidence and recovery/rollback proof | `architecture/phase7c_live_evidence_contract.json` + gated workflow | IN_PROGRESS |
| Phase 7C same-VPC migration runner | task-mode Serverless Container on the same immutable image digest and VPC; Lockbox database secret; CI-only invoker; no API Gateway/public access | `tests/test_phase7c_live_evidence_contract.py` + Terraform gate + live task exit-code/log evidence | IN_PROGRESS |
| Phase 6 Web/PWA consolidation | one same-origin Web/PWA experience over canonical APIs; server-authoritative capabilities; no browser business persistence; explicit `NOT_COMPOSED` handoff without external success claims; operator route fails closed after capability rejection | `tests/test_phase6_operator_consolidation_acceptance.py` + full seven-job release gate `36637312890` on HEAD `1b75bfb46f73309597420b4e1b7762c1477a1e8c` | CLOSED / VERIFIED |
| Web/public/operator trust boundary |
| Repeat-order activation trust boundary | capability is advertised only when a real server-side RepeatOrderService/Revalidator is composed; browser cannot replace validation | fail-closed capability/API tests; idempotency and canonical endpoint tests | full current-head gate |
| Web/public/operator trust boundary | same-origin shell/assets only; business API remains server-authenticated; capability visibility is server-advertised; operator token is page-memory only | public shell vs protected API tests; browser-storage and direct-DB negative tests | current-head full release gate |
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

# Security Certification Matrix — v1.5

This matrix certifies the security controls already implemented in the unified v1.5 runtime. It does not introduce new security semantics.

| Control | Implementation | Fail-closed / failure behavior | Executable evidence | Release gate |
|---|---|---|---|---|
| OIDC issuer HTTPS | `OIDCConfiguration`, `RuntimeSecurityConfiguration` | HTTP issuer rejected | `tests/test_oidc_authentication.py`, `tests/test_runtime_security.py` | quality + release-contract |
| OIDC JWKS HTTPS | OIDC/runtime security configuration | HTTP JWKS rejected | OIDC/security tests | quality + release-contract |
| Explicit asymmetric JWT algorithms | OIDC adapter allow-list | non-approved algorithm rejected | OIDC authentication tests | quality + release-contract |
| JWT issuer/audience/expiry/sub validation | OIDC adapter | invalid/missing claims reject authentication | OIDC authentication tests | quality + integration |
| Bounded JWKS caching | PyJWT JWKS provider | cache is bounded by configured lifetime/key count | OIDC adapter implementation review | security review + release-contract |
| Permission materialization | OIDC adapter → authenticated actor | unknown permission rejects authentication | OIDC unknown-permission test | quality + release-contract |
| Authorization before critical action | RBAC + application workflow | permission denial blocks mutation | critical workflow/API tests | quality + integration |
| Production docs disabled | runtime startup security | production startup fails closed | runtime security tests | quality + release-contract |
| Production OIDC configuration required | runtime startup security | missing/unsafe issuer, audience or JWKS rejects startup | runtime security tests | quality + release-contract |
| Development DB default forbidden in production | runtime startup security | unsafe development DB URL rejects startup | runtime security tests | quality + release-contract |
| Telemetry allow-list redaction | telemetry sanitizer | non-allow-listed attributes omitted | telemetry unit + B6 integration test | quality + integration |
| Authorization headers excluded from telemetry | telemetry sanitizer | auth header never emitted | telemetry tests + B6 integration test | quality + integration |
| Request bodies excluded from telemetry | telemetry sanitizer | request body never emitted | telemetry tests + B6 integration test | quality + integration |
| Correlation propagation | API middleware → RequestContext → audit + telemetry | missing/invalid lineage is observable; canonical truth remains DB/audit | B6 PostgreSQL integration test | integration |
| Dependency vulnerability gate | CI `pip-audit --strict` | dependency vulnerability fails CI | supply-chain job | release gate |
| Historical migration integrity | checksummed migration ledger | modified historical migration fails closed | migration tests | release-contract + integration |
| Recovery controls | durable jobs, leases, outbox, commercial send | crash/retry converges without duplicate canonical effect | recovery drills + B4 | integration + backup-recovery |
| Production PITR recovery | PostgreSQL backup/WAL/recovery drill | recovery failure blocks release | B5 `backup-recovery` job | release gate |

## Certification result

All controls in this matrix are **implemented and executablely evidenced** on PR #8's unified v1.5 candidate.

The matrix is a certification artifact, not a substitute for runtime enforcement. PostgreSQL remains canonical transactional authority; IAM, telemetry, external providers and CI controls remain bounded adapters/gates around that authority.

Last verified security evidence:
- unified candidate CI: #989
- measured recovery gate: #1005
- end-to-end observability proof: #1011

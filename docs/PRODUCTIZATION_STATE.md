# Productization State

## Current verified context

- Repository: `LIK-HO/shema-business-platform`
- Productization branch: `v1.5/productization-iam`
- Frozen core baseline: `a3eec47ea68882631ebf24b3998b431f2dc83600`
- Current productization HEAD: `8c6fbe74c46e16872c1fc9660536757e5b05778d`
- Core PR: #8 — open, draft, unmerged
- Productization PR: #9 — open, draft, unmerged
- v1.4 kernel semantics: frozen
- v1.5 core maturity: certified

## P1 — PRODUCTION IAM BOOTSTRAP — CLOSED / VERIFIED

Purpose:
- compose the provider-neutral OIDC authenticator automatically in production;
- load required OIDC runtime configuration from environment;
- fail closed when mandatory OIDC configuration is absent;
- preserve explicit authenticator injection as a composition/test override.

Implementation:
- `OIDCConfiguration.from_environment()` reads issuer, audience and JWKS URL;
- `create_app()` auto-wires `OIDCJWTAuthenticator.production(...)` only for production when no explicit authenticator was supplied;
- existing HTTPS, audience, algorithm, expiry and permission validation remains authoritative;
- no domain, persistence, idempotency, outbox, order or economics semantics changed.

Evidence:
- CI run #1039 (`35893961503`) passed all seven required jobs:
  - quality 3.12 — success;
  - quality 3.13 — success;
  - integration 3.12 — success;
  - integration 3.13 — success;
  - supply-chain — success;
  - backup-recovery — success;
  - release-contract — success.

Changed boundary:
- `src/shema_platform/adapters/iam/oidc.py`
- `src/shema_platform/experience/api.py`
- `tests/test_oidc_authentication.py`
- `tests/test_runtime_security.py`

The productization change is intentionally stacked on PR #8 and does not authorize merge or deployment.

## Next safe boundary

Next product work may proceed only outside the frozen kernel.

External provider rule:
- a provider may not redefine canonical business truth;
- external send/retry behavior must have a demonstrated reconciliation or idempotency mechanism before live activation;
- no unsafe provider integration is promoted merely because an API exists.

Current MAX outbound status:
- adapter contract and deterministic mock exist;
- live outbound activation remains a separate bounded integration task pending proof of safe external-effect reconciliation compatible with the kernel's crash/retry semantics.

## Stop condition

Do not reopen v1.4/v1.5 core semantics for productization convenience.

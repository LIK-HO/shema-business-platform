# Productization State

## Current verified context

- Repository: `LIK-HO/shema-business-platform`
- Productization branch: `v1.5/productization-provider-safety`
- Frozen core baseline: `a3eec47ea68882631ebf24b3998b431f2dc83600`
- Current productization HEAD: `fe875dd7a7f6045e1a95adc608b4235da6402745`
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

## P2 — PRODUCTION STRUCTURED OBSERVABILITY — CLOSED / VERIFIED

Purpose:
- compose a real operational telemetry sink in production without making telemetry authoritative;
- preserve the existing correlation and attribute-redaction contract;
- ensure telemetry backend failure cannot break the request path.

Implementation:
- `StructuredLoggingTelemetrySink` emits one redacted JSON record per telemetry event;
- production `create_app()` composes the structured sink by default;
- explicit telemetry injection remains supported for tests and controlled composition;
- the existing allow-list remains the only source of emitted attributes;
- sink failures are swallowed because operational telemetry is non-authoritative.

Evidence:
- CI run #1043 (`35894711738`) passed all seven required jobs:
  - quality 3.12 — success;
  - quality 3.13 — success;
  - integration 3.12 — success;
  - integration 3.13 — success;
  - supply-chain — success;
  - backup-recovery — success;
  - release-contract — success.

Changed boundary:
- `src/shema_platform/foundation/telemetry.py`
- `src/shema_platform/experience/api.py`
- `tests/test_telemetry.py`
- `tests/test_runtime_security.py`

No kernel semantic change was made.

## Next bounded productization boundary

P3 — external-provider safety boundary.

The next implementation must prove provider capabilities before any live external effect is activated. A provider adapter may expose health/configuration and explicit capability metadata, but it must not be treated as crash-safe merely because it has a send endpoint.

For MAX specifically, live outbound send remains blocked until an evidence-backed reconciliation/idempotency mechanism is established that is compatible with the kernel's crash/retry semantics.

No merge or deployment authorization is implied by these productization PRs.

## P3 — EXTERNAL-EFFECT PROVIDER SAFETY — CLOSED / VERIFIED

Purpose:
- fail closed before any live external effect when provider retry safety is not proven;
- require an evidence reference for external-effect capability claims;
- keep provider capability assessment outside the frozen kernel;
- prevent a send endpoint from being mistaken for crash-safe idempotency.

Implementation:
- `ExternalEffectSafety` represents explicit provider capabilities for idempotency and deterministic reconciliation;
- `require_safe_external_effect()` requires at least one proven retry-safety capability;
- `SafeCommunicationAdapter` refuses composition of uncertified providers with `QuarantineRequired`;
- the deterministic `MaxAdapter` remains a test/local adapter and carries no live-provider certification metadata.

MAX assessment:
- published MAX `POST /messages` documentation does not document an idempotency key or equivalent request-deduplication field;
- published `GET /messages` supports retrieval by chat/message identifiers but does not document reconciliation by this platform's durable external-effect key;
- therefore live MAX outbound remains blocked until provider-side idempotency or deterministic reconciliation is proven.

Evidence:
- CI run #1049 (`35895711976`) passed all seven required jobs:
  - quality 3.12 — success;
  - quality 3.13 — success;
  - integration 3.12 — success;
  - integration 3.13 — success;
  - supply-chain — success;
  - backup-recovery — success;
  - release-contract — success.

Changed boundary:
- `src/shema_platform/adapters/communication/safety.py`
- `tests/test_provider_safety.py`
- `docs/MAX_PROVIDER_SAFETY.md`
- `src/shema_platform/adapters/communication/max.py` (kept as deterministic adapter without live-effect certification metadata)

No kernel or application workflow semantic change was made.

## Productization boundary after P3

The core and the first three productization controls are now bounded:
- P1 — production IAM bootstrap — closed;
- P2 — production structured observability — closed;
- P3 — external-effect provider safety — closed.

No new core phase is created. Further product work remains outside the frozen kernel and must have its own bounded evidence gate. Live MAX outbound remains explicitly blocked pending provider capability proof.

No merge or deployment authorization is implied by these productization PRs.

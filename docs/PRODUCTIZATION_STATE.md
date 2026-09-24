# Productization State

## Current verified context

- Repository: `LIK-HO/shema-business-platform`
- Productization branch: `v1.5/productization-provider-failure-path`
- Frozen core baseline: `a3eec47ea68882631ebf24b3998b431f2dc83600`
- Current productization HEAD: `66381f2daf27a0335cd8ae355bdc1762878d3dbb`
- Core PR: #8 — open, draft, unmerged
- Productization PR: #24 — open, draft, unmerged
- Active productization phase: P15 — provider failure-path materialization guard
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

## P4 — REAL INTELLIGENCE PROVIDER: OPENCORPORATES — CLOSED / VERIFIED

Purpose:
- add one concrete production-capable intelligence provider behind the existing `ResearchProvider` / `ProviderCapability` boundary;
- preserve canonical business truth in the platform and convert provider observations only into the existing evidence flow;
- make provider configuration explicit, bounded and fail-closed without automatic production activation.

Implementation:
- `OpenCorporatesConfiguration` loads a required API token and explicit operational limits from environment configuration;
- `OpenCorporatesProvider` performs read-only HTTPS company search against the versioned `/v0.4/companies/search` endpoint;
- each materialized claim requires an HTTPS OpenCorporates provenance URL;
- each call is capped at 50 provider results and locally throttled;
- non-200 responses and malformed JSON fail closed;
- external I/O remains outside Unit of Work, preserving the existing intelligence transaction boundary;
- no canonical identity/order/economics state is mutated by the provider;
- production auto-activation remains disabled.

External contract evidence:
- OpenCorporates documents its versioned REST API, API-key authentication, HTTPS usage, version 0.4 company search endpoint, provenance/source URLs and plan-dependent usage limits.
- Reference recorded in `docs/OPENCORPORATES_PROVIDER.md`.

Evidence:
- CI run `35897370730` passed all seven required jobs:
  - quality 3.12 — success;
  - quality 3.13 — success;
  - integration 3.12 — success;
  - integration 3.13 — success;
  - supply-chain — success;
  - backup-recovery — success;
  - release-contract — success.

Changed boundary:
- `src/shema_platform/adapters/intelligence/opencorporates.py`
- `tests/test_opencorporates_provider.py`
- `architecture/opencorporates_provider_contract.json`
- `docs/OPENCORPORATES_PROVIDER.md`

No kernel or existing intelligence workflow semantics were changed.

## Next bounded productization boundary

P5 — EXPLICIT PROVIDER ACTIVATION / CONFIGURATION SNAPSHOT.

The next step is not live activation itself. It is to add a controlled composition boundary that can instantiate an explicitly enabled OpenCorporates provider from a versioned configuration snapshot, while remaining fail-closed when the provider is not enabled or its secret configuration is absent.

No provider may become authoritative through activation. No merge or deployment authorization is implied.

## P5 — EXPLICIT PROVIDER ACTIVATION / CONFIGURATION SNAPSHOT — CLOSED / VERIFIED

Purpose:
- create a controlled composition boundary for the verified OpenCorporates adapter;
- require explicit feature enablement before composition;
- keep provider secrets outside versioned configuration snapshots;
- fail closed on missing secrets or invalid operational values.

Implementation:
- `OpenCorporatesProviderFactory` composes the adapter only when the versioned snapshot carries `intelligence.opencorporates.enabled=true`;
- runtime API token is supplied separately and is never copied into `ConfigurationSnapshot`;
- provider operational settings come from the snapshot and are validated by the existing provider configuration contract;
- disabled providers are not composed;
- missing runtime secret causes fail-closed activation failure;
- no production auto-activation or deployment infrastructure change was introduced.

Evidence:
- CI run `35897892691` passed all seven required jobs:
  - quality 3.12 — success;
  - quality 3.13 — success;
  - integration 3.12 — success;
  - integration 3.13 — success;
  - supply-chain — success;
  - backup-recovery — success;
  - release-contract — success.

Changed boundary:
- `src/shema_platform/adapters/intelligence/activation.py`
- `tests/test_opencorporates_activation.py`
- `architecture/opencorporates_activation_contract.json`
- `docs/OPENCORPORATES_ACTIVATION.md`

No kernel, canonical business truth, evidence persistence, or research-routing semantics were changed.

## Next bounded productization boundary

P6 — PRODUCTION OBSERVABILITY / HEALTH READINESS FOR EXTERNAL PROVIDERS.

The next step is to expose provider readiness as operational health information without turning provider health into canonical business truth: configuration presence, enabled/disabled state, dependency reachability metadata and last-known failure state, with secrets and response payloads excluded.

No merge or deployment authorization is implied.

## P6 — PROVIDER HEALTH / READINESS — CLOSED / VERIFIED

Purpose:
- expose provider operational readiness without turning provider health into canonical business truth;
- keep health state bounded to configuration, enablement, reachability, timestamp and error code;
- provide a secret-free unauthenticated readiness surface for orchestration.

Implementation:
- `ProviderHealthRegistry` is process-local and stores no secrets or provider response payloads;
- disabled providers are considered ready by policy;
- enabled providers are ready only when configured and positively reachable;
- unknown/unconfigured/unreachable enabled providers make readiness fail closed;
- `GET /health/ready` returns HTTP 200 when all enabled providers are ready and 503 otherwise;
- authentication is intentionally bypassed only for this operational endpoint;
- response contains bounded provider metadata only, with no API tokens, authorization headers, request bodies or provider claims;
- a pre-existing PITR drill readiness race discovered during certification was hardened with Docker health-check based PostgreSQL source readiness and bounded diagnostics; no business/runtime semantics changed.

Evidence:
- Final CI run #1062 (`35898648431`) passed all seven required jobs:
  - quality 3.12 — success;
  - quality 3.13 — success;
  - integration 3.12 — success;
  - integration 3.13 — success;
  - supply-chain — success;
  - backup-recovery — success;
  - release-contract — success.

Changed boundary:
- `src/shema_platform/foundation/provider_health.py`
- `src/shema_platform/experience/api.py`
- `tests/test_provider_health.py`
- `tests/test_runtime_security.py`
- `architecture/provider_health_contract.json`
- `docs/PROVIDER_HEALTH.md`
- `scripts/postgres_pitr_drill.sh` (CI readiness hardening only)

No kernel semantics, canonical business truth, provider intelligence semantics or persistence ownership were changed.

## Next bounded productization boundary

P7 — EXPLICIT PROVIDER READINESS PROBES.

The next step is to connect the health registry to provider-specific, non-business probes. A probe may verify configuration and transport reachability, update only operational health state and emit existing telemetry; it must not fetch or persist business claims, secrets or canonical data.

No merge or deployment authorization is implied.

## P7 — EXPLICIT PROVIDER READINESS PROBES — CLOSED / VERIFIED

Purpose:
- connect provider-specific transport probes to the P6 operational health registry without running them implicitly from health checks;
- keep probe evidence strictly operational and non-business;
- use the existing non-authoritative telemetry boundary for probe outcomes.

Implementation:
- `ProviderReadinessProbe` / `ProviderProbeRunner` provide the generic explicit probe boundary;
- disabled providers are never probed;
- successful probes update only provider reachability and check time;
- failed probes update only bounded error codes and emit safe telemetry metadata;
- exceptions and provider response bodies are never persisted or emitted;
- OpenCorporates probe uses the versioned HTTPS endpoint with a dedicated readiness query, requests at most one result, and evaluates HTTP status without parsing the returned body;
- `/health/ready` remains probe-free and therefore cheap/deterministic.

Evidence:
- CI run #1064 (`35899255814`) passed all seven required jobs:
  - quality 3.12 — success;
  - quality 3.13 — success;
  - integration 3.12 — success;
  - integration 3.13 — success;
  - supply-chain — success;
  - backup-recovery — success;
  - release-contract — success.

Changed boundary:
- `src/shema_platform/foundation/provider_probe.py`
- `src/shema_platform/adapters/intelligence/opencorporates.py`
- `tests/test_provider_probe.py`
- `architecture/provider_probe_contract.json`
- `docs/PROVIDER_READINESS_PROBES.md`

No kernel, canonical business, intelligence routing or persistence semantics were changed.

## Next bounded productization boundary

P8 — INTELLIGENCE PROVIDER RESOURCE / COST GUARD.

The next step is to enforce bounded external intelligence consumption per operation: provider call budget, request-rate budget and explicit rejection before external I/O when the budget is exhausted. The guard will be operational policy only and will not become canonical economic state.

No merge or deployment authorization is implied.


## P8 — INTELLIGENCE PROVIDER RESOURCE / COST GUARD — CLOSED / VERIFIED

Purpose:
- enforce an explicit operation-scoped bound on external provider calls;
- reject before external I/O when the bound is exhausted;
- keep the guard process-local and operational rather than turning it into canonical economic state.

Implementation:
- `ProviderBudget` validates non-negative call limits and positive provider request-rate configuration;
- `ProviderCallBudget` tracks calls for one operation and reserves a call before external I/O;
- `ProviderBudgetExceeded` fails closed when the explicit call budget is exhausted;
- OpenCorporates accepts an optional typed call budget and reserves before invoking the requester;
- the provider's existing request-rate throttle remains authoritative for provider-specific rate control;
- no durable spend ledger, billing semantics, global/distributed limiter, retry scheduler or kernel change was introduced.

Evidence:
- Final CI run #1066 (`35906662100`) passed all seven required jobs:
  - quality 3.12 — success;
  - quality 3.13 — success;
  - integration 3.12 — success;
  - integration 3.13 — success;
  - supply-chain — success;
  - backup-recovery — success;
  - release-contract — success.

Changed boundary:
- `src/shema_platform/foundation/provider_budget.py`
- `src/shema_platform/adapters/intelligence/opencorporates.py`
- `tests/test_provider_budget.py`
- `architecture/provider_budget_contract.json`
- `docs/PROVIDER_RESOURCE_BUDGET.md`

No kernel semantics, canonical business truth, durable economics, global limiting or deployment behavior were changed.

## Next bounded productization boundary

P9 — PROVIDER OPERATION EXECUTION POLICY.

The next step is to bound the execution envelope around an external provider operation: explicit timeout/deadline policy and bounded failure handling, without introducing a retry scheduler, durable job semantics or new kernel behavior. The policy must remain outside the frozen kernel and must fail closed rather than permit unbounded external work.

No merge or deployment authorization is implied.


## P9 — PROVIDER OPERATION EXECUTION POLICY — CLOSED / VERIFIED

Purpose:
- bound the execution envelope of the external OpenCorporates operation;
- fail closed on non-positive or over-limit timeout configuration;
- keep the execution policy outside the frozen kernel.

Implementation:
- OpenCorporates provider timeout is explicitly bounded to a maximum of 30 seconds;
- the bounded timeout is passed directly to the external requester;
- timeout values above the contract are rejected before external I/O;
- focused tests prove both rejection of an over-limit timeout and propagation of the 30-second boundary;
- no automatic retry, scheduler, durable job semantics, global limiter or kernel change was introduced.

Evidence:
- CI run #1076 (`35907917054`) passed all seven required jobs:
  - quality 3.12 — success;
  - quality 3.13 — success;
  - integration 3.12 — success;
  - integration 3.13 — success;
  - supply-chain — success;
  - backup-recovery — success;
  - release-contract — success.

Changed boundary:
- `src/shema_platform/adapters/intelligence/opencorporates.py`
- `tests/test_opencorporates_provider.py`
- `architecture/provider_execution_policy_contract.json`
- `docs/PROVIDER_OPERATION_EXECUTION_POLICY.md`

No kernel, canonical business-truth, persistence, retry-scheduler or deployment semantics were changed.
No merge or deployment authorization is implied.

## Next bounded productization boundary

P10 — RESEARCH EXECUTION DEADLINE PROPAGATION.

The next bounded control should connect the already-existing `ResearchBudget.time_budget_seconds` to actual provider execution, so a provider operation cannot outlive the remaining research time budget. This must remain outside the frozen kernel, preserve the existing provider budget/cost gates, avoid automatic retries and durable-job semantics, and prove timeout propagation with focused tests.

## P10 — RESEARCH EXECUTION DEADLINE — CLOSED / VERIFIED

Purpose:
- bind the existing operation-scoped research time budget to actual external provider execution;
- prevent a provider operation from receiving a timeout larger than the remaining research budget;
- keep execution deadline control outside the frozen kernel.

Implementation:
- `ResearchBudget.time_budget_seconds` is propagated as the remaining provider execution timeout;
- OpenCorporates uses the smaller of its configured provider timeout and the propagated research deadline;
- provider execution is skipped once no research time remains;
- non-positive explicit provider deadline overrides fail closed;
- focused gateway, provider and integration tests cover deadline propagation and enforcement;
- no automatic retry, scheduler, durable job semantics, global limiter, billing ledger or kernel change was introduced.

Evidence:
- CI run #1081 (`35909122007`) passed all seven required jobs:
  - quality 3.12 — success;
  - quality 3.13 — success;
  - integration 3.12 — success;
  - integration 3.13 — success;
  - supply-chain — success;
  - backup-recovery — success;
  - release-contract — success.

Changed boundary:
- `src/shema_platform/application/research.py`
- `src/shema_platform/adapters/intelligence/opencorporates.py`
- `tests/test_research.py`
- `tests/test_opencorporates_provider.py`
- `tests/test_intelligence.py`
- `tests/test_research_ai.py`
- `tests/integration/test_intelligence_postgres.py`
- `architecture/research_execution_deadline_contract.json`
- `docs/RESEARCH_EXECUTION_DEADLINE.md`

No kernel, canonical business-truth, persistence, retry-scheduler or deployment semantics were changed.
No merge or deployment authorization is implied.

## P11 — RESEARCH WALL-CLOCK DEADLINE — CLOSED / VERIFIED

Purpose:
- make the research operation's elapsed-time budget authoritative from a monotonic wall-clock deadline;
- prevent provider-reported latency metadata from extending the execution envelope;
- keep the deadline control outside the frozen kernel.

Implementation:
- the gateway captures a monotonic deadline at the start of the provider waterfall;
- before each provider call, the actual remaining wall-clock budget is recomputed;
- provider execution receives that remaining time as its timeout cap;
- provider-reported `latency_seconds` remains usage metadata and cannot extend the deadline;
- when the wall-clock budget is exhausted, no further provider executes;
- focused regression coverage proves the deadline shrinks with elapsed wall-clock time;
- no automatic retry, scheduler, durable job semantics, global limiter, billing ledger or kernel change was introduced.

Evidence:
- CI run #1086 (`35910036890`) passed all seven required jobs:
  - quality 3.12 — success;
  - quality 3.13 — success;
  - integration 3.12 — success;
  - integration 3.13 — success;
  - supply-chain — success;
  - backup-recovery — success;
  - release-contract — success.

Changed boundary:
- `src/shema_platform/application/research.py`
- `tests/test_research.py`
- `architecture/research_wall_clock_contract.json`
- `docs/RESEARCH_WALL_CLOCK_DEADLINE.md`

No kernel, canonical business-truth, persistence, retry-scheduler or deployment semantics were changed.
No merge or deployment authorization is implied.

## P12 — PROVIDER PRE-I/O DEADLINE — CLOSED / VERIFIED

Purpose:
- include provider-local rate-limit waiting inside the same execution deadline;
- fail closed before external I/O when the required pre-I/O wait cannot fit inside the remaining budget;
- pass only the post-wait timeout to the actual HTTP requester.

Implementation:
- OpenCorporates derives a monotonic deadline from the effective timeout;
- rate-limit sleep is permitted only when it fits within that deadline;
- if the wait would consume the remaining deadline, the provider raises before external I/O;
- after a bounded wait, the requester receives only the remaining timeout;
- focused tests prove timeout reduction and fail-closed pre-I/O behavior;
- no retry scheduler, durable job semantics, global limiter, billing ledger or kernel change was introduced.

Evidence:
- CI run #1090 (`35910936638`) passed all seven required jobs:
  - quality 3.12 — success;
  - quality 3.13 — success;
  - integration 3.12 — success;
  - integration 3.13 — success;
  - supply-chain — success;
  - backup-recovery — success;
  - release-contract — success.

Changed boundary:
- `src/shema_platform/adapters/intelligence/opencorporates.py`
- `tests/test_opencorporates_provider.py`
- `architecture/provider_preio_deadline_contract.json`
- `docs/PROVIDER_PREIO_DEADLINE.md`

No kernel, canonical business-truth, persistence, retry-scheduler or deployment semantics were changed.
No merge or deployment authorization is implied.


## P13 — PROVIDER RESPONSE SIZE CAP — CLOSED / VERIFIED

Purpose:
- bound the maximum external provider response payload;
- enforce the response limit at both the HTTP transport and adapter boundary;
- fail closed before JSON materialization when the configured response ceiling is exceeded.

Implementation:
- OpenCorporates uses a 1 MiB default response ceiling with a hard 4 MiB configuration maximum;
- the HTTP transport reads at most max_response_bytes + 1 bytes and rejects oversized responses before returning them to the adapter;
- the adapter rechecks the returned byte length before JSON parsing, protecting the existing injected/requester test seam as well;
- readiness probes use the same bounded transport path;
- focused tests cover non-positive and over-cap configuration, transport-level rejection and adapter-level rejection;
- no kernel, retry scheduler, durable job semantics, global limiter, billing ledger or deployment semantic was introduced.

Evidence:
- CI run #1093 (35995465195) passed all seven required jobs:
  - quality 3.12 — success;
  - quality 3.13 — success;
  - integration 3.12 — success;
  - integration 3.13 — success;
  - supply-chain — success;
  - backup-recovery — success;
  - release-contract — success.

During verification, the first P13 candidate failed six existing unit tests because it changed the injected requester callable signature. The bounded implementation was corrected to preserve the pre-existing three-argument requester contract; the final CI run then passed all seven gates.

Changed boundary:
- src/shema_platform/adapters/intelligence/opencorporates.py
- tests/test_opencorporates_provider.py
- architecture/provider_response_size_contract.json
- docs/PROVIDER_RESPONSE_SIZE_LIMIT.md

No kernel, canonical business-truth, persistence, retry-scheduler or deployment semantics were changed.
No merge or deployment authorization is implied.

## Next bounded productization boundary

P14 — PROVIDER REQUEST-INPUT ENVELOPE.

The next boundary is to bound the input side of concrete provider calls: query size and the resulting outbound request envelope before external I/O, while preserving the existing ResearchProvider contract and avoiding provider-specific semantics in the kernel. First verify the current upstream/provider request limits and existing application validation, then implement the smallest compatible fail-closed bound.

No merge or deployment authorization is implied.


## P14 — PROVIDER REQUEST-INPUT ENVELOPE — CLOSED / VERIFIED

Purpose:
- bound the input side of a concrete external provider operation;
- reject oversized provider queries and oversized encoded GET request envelopes before rate-limit waiting and external I/O;
- preserve the existing three-argument requester seam and keep the control outside the frozen kernel.

Implementation:
- OpenCorporates query input is required to be a string, trimmed before validation, and capped at 1,024 Unicode characters by default;
- configurable query limit is hard-capped at 4,096 characters;
- the complete encoded request URL is capped at 8,192 bytes by default and 16,384 bytes maximum;
- the pre-I/O envelope check occurs before provider throttling;
- the HTTP transport repeats the request-URL bound immediately before urlopen;
- readiness probes use the same request-envelope bound;
- focused tests prove fail-closed behavior, no requester invocation on oversized input, configuration hard caps and compatibility with the existing requester seam;
- no kernel, retry scheduler, durable job, global limiter, billing ledger or deployment semantic was introduced.

Evidence:
- CI run #1097 (35997442399) passed all seven required jobs:
  - quality 3.12 — success;
  - quality 3.13 — success;
  - integration 3.12 — success;
  - integration 3.13 — success;
  - supply-chain — success;
  - backup-recovery — success;
  - release-contract — success.

During verification, the first candidate exposed one lint-only test defect and the next candidate exposed one incorrect test threshold; both were corrected without changing production semantics. Final CI #1097 was fully green on HEAD 18322ce554511ea56cc36662a7cbac7cda47dd48.

Changed boundary:
- src/shema_platform/adapters/intelligence/opencorporates.py
- tests/test_opencorporates_provider.py
- architecture/provider_request_input_contract.json
- docs/PROVIDER_REQUEST_INPUT_ENVELOPE.md

No kernel, canonical business-truth, persistence, retry-scheduler or deployment semantics were changed.
No merge or deployment authorization is implied.

## Next bounded productization boundary

P15 — PROVIDER FAILURE-PATH MATERIALIZATION GUARD.

The next boundary is to make non-success HTTP responses fail before JSON materialization in the concrete provider adapter. This keeps bounded error bodies from being parsed as business payloads, preserves the existing fail-closed status semantics, and remains entirely outside the frozen kernel. No automatic retry or provider-specific business interpretation should be introduced.

No merge or deployment authorization is implied.


## P15 — PROVIDER FAILURE-PATH MATERIALIZATION GUARD — CLOSED / VERIFIED

Purpose:
- reject non-success OpenCorporates HTTP responses before JSON materialization;
- preserve the existing fail-closed ConnectionError semantics while keeping response-size enforcement intact;
- prevent bounded provider error bodies from entering the business-payload parser.

Implementation:
- response size remains checked first;
- HTTP status is evaluated before json.loads();
- non-200 responses fail immediately with the existing ConnectionError contract;
- only HTTP 200 responses proceed to JSON materialization;
- readiness probes retain their operational-only behavior;
- focused regression coverage proves a non-JSON 503 response fails as HTTP 503 rather than being reported as invalid JSON;
- no retry scheduler, automatic retry, durable job semantics, billing ledger, or kernel semantic was introduced.

Evidence:
- CI run #1099 (`35997915177`) passed all seven required jobs:
  - quality 3.12 — success;
  - quality 3.13 — success;
  - integration 3.12 — success;
  - integration 3.13 — success;
  - supply-chain — success;
  - backup-recovery — success;
  - release-contract — success.

Changed boundary:
- src/shema_platform/adapters/intelligence/opencorporates.py
- tests/test_opencorporates_provider.py
- architecture/opencorporates_provider_contract.json
- docs/PROVIDER_FAILURE_PATH_MATERIALIZATION.md

No kernel, canonical business-truth, persistence, retry-scheduler or deployment semantics were changed.
No merge or deployment authorization is implied.

## Next bounded productization boundary

P16 — PROVIDER PROVENANCE HOST VALIDATION.

The next boundary is to validate that materialized OpenCorporates provenance URLs actually resolve to the expected OpenCorporates host rather than merely any HTTPS origin. This is an evidence-integrity guard at the concrete adapter boundary; it must not promote external provenance into canonical truth or change frozen kernel semantics.

No merge or deployment authorization is implied.

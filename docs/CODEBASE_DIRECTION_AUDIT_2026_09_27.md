# Shema Business Platform — Codebase Direction Audit

## Date
2026-09-27

## Baseline

Audited the current v1.5 development line around P45/P46, the frozen v1.4 kernel, Phase 2 search/research boundaries, provider registry, adapter compliance/readiness contracts, runtime composition, canonical API surface, deterministic tests, and the newly selected DaData alternative.

The audit goal is a vector check: does the implemented architecture continue toward a mature personal operating system without reopening the frozen kernel or accumulating blind provider-specific coupling?

## 1. What is already strong

### A. Stable core / extension model
The v1.4 kernel is explicitly frozen and new capabilities are placed in application, adapter, integration and experience layers.
Result: aligned.

### B. Search decomposition
Search is separated into criteria, source registry, planned source order, adapter compliance, bounded run execution, explicit completeness, and identity/evidence after discovery. The code does not require a global ranking score to make the search path work.
Result: aligned.

### C. Truth and provenance
The architecture separates source reliability, claim confidence, freshness, evidence and canonical identity. A provider response is not automatically business truth.
Result: aligned.

### D. Durable execution / recovery
The broader v1.5 kernel already contains durable jobs, leases, reclaim, bounded retry, outbox semantics and state invariants. The new provider boundary can reuse existing reliability mechanisms rather than invent a second worker model.
Result: aligned.

### E. Observability
Correlation is already a first-class runtime concept, and the canonical API includes X-Correlation-Id. Provider work should continue this lineage rather than introduce provider-local trace systems.
Result: aligned.

### F. External-call safety
The kernel's commercial-send path uses durable idempotency and refuses to assume exactly-once behavior across a network. That is consistent with production API practice such as Stripe idempotency keys.
Result: aligned.

## 2. Main vector correction
The original Phase 2 roadmap stopped at FNS evidence and had no explicit next provider-execution boundary.
This created a design risk: a documented automation provider could exist, while the roadmap gave the project no formal place to prove a controlled provider adapter.

Correction applied: Phase 2-H is now an explicit controlled-execution boundary, with DaData as the parallel alternative and FNS remaining separately blocked.

## 3. DaData fit
DaData's organization API documents a POST endpoint, token authentication, INN/INN+KPP/OGRN lookup, request/count limits, daily quota by tariff, 30 requests/second per IP, 60 new connections/minute per IP, and HTTP error classes including 429 and 5xx.
DaData also documents multiple underlying data sources, including EGRUL/EGRIP and other official/structured datasets. That supports the trusted_secondary classification, not authoritative.

## 4. Gaps still to implement
1. Provider adapter implementation behind the generic SearchProvider.
2. Application timeout and retry layer. Provider docs do not establish provider-specific timeout or Retry-After semantics; those remain application policy and explicit unknowns.
3. Secret boundary. API key comes from deployment configuration/secret storage, never source control; missing-secret and redaction behavior must be tested.
4. Deterministic fixtures for success, no-match, invalid input, missing/invalid key, daily-limit exhaustion, 429, 5xx, timeout and malformed payload.
5. Integration gate with live network disabled in CI and explicit partial-source completeness.
6. A distinct Phase 2-H activation contract. Phase 2-F readiness is intentionally not the live-execution switch.

## 5. Mature-system correspondence check
| Concern | Shema direction | Mature-system pattern | Vector |
|---|---|---|---|
| Idempotent external effects | durable idempotency + state machine | Stripe idempotency keys | aligned |
| Durable work | jobs + lease/reclaim + retry | Temporal durable execution | aligned |
| Remote retries | bounded policy, provider-aware classification | AWS backoff/jitter guidance | aligned |
| Provenance | evidence/source/date/context | OpenLineage run/input/output lineage | aligned |
| Observability | correlation across API/workflow/audit | OpenTelemetry context + log correlation | aligned |
| Connector modularity | source registry + adapter boundary | Airbyte connector model | aligned |
| Provider neutrality | generic SearchProvider | connector/provider abstraction | aligned |

## 6. What should not be built now
- microservices;
- a separate provider database;
- a global opaque relevance score;
- a graph database;
- automatic qualification;
- a second identity system;
- FNS scraping;
- silent fallback chains that switch evidence sources;
- provider-specific business rules inside domain code;
- live CI credentials or live provider traffic.

## 7. Direction decision
Current development vector is correct, with one required correction now applied.

Recommended order: Phase 2-H → DaData provider-neutral counterparty-lookup adapter → deterministic failure matrix → evidence pipeline integration → controlled activation gate → identity/search quality benchmark → broader provider expansion.

FNS remains a parallel authoritative-source track, but becomes automatable only when its own provider-specific contract is evidenced.

DaData does not replace FNS. It gives the architecture a second, independently governed path and lets the project prove that provider-specific execution can be added without breaking the frozen kernel.

## 8. Audit limitation
The GitHub connector exposed the current PR changed-file set and the relevant provider/search architecture directly, but a full raw clone was not available in the execution environment. This report therefore does not claim a byte-for-byte inspection of every historical repository file.

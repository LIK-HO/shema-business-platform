# Phase 2-H — Controlled Provider Execution Boundary: DaData

## Status

DEFINED / IMPLEMENTATION BOUNDARY OPEN / LIVE ACTIVATION OFF

Phase 2-H introduces the first provider-specific execution boundary after the provider-neutral Phase 2-A..2-F contracts and the Phase 2-G evidence work.

### Parallel provider tracks

| Provider | Role | Current state |
|---|---|---|
| DaData | documented API alternative | controlled-execution candidate |
| FNS Transparent Business | authoritative public-source alternative | evidence hold / BLOCKED for automation |

The tracks are parallel in architecture and evidence management, not simultaneous live traffic.

## Why DaData is admissible for this boundary

DaData publishes a machine-readable organization lookup API, API-key authentication, request constraints, daily quota model and HTTP error classes. It also documents 30 requests/second per IP and 60 new connections/minute per IP. The current free tier is documented as 10,000 requests/day.

## Authority rule

DaData is not the canonical authority.

It is registered as:
- source class: trusted_structured_dataset;
- reliability: trusted_secondary;
- access mode: approved_adapter_only.

Its output may contribute to candidate discovery, identifier resolution and enrichment. Existing Evidence and Identity contracts remain responsible for canonical truth and conflict handling.

## Execution boundary

The implementation is deliberately split from discovery:

provider-neutral CounterpartyLookupProvider
→ DaData lookup adapter
→ provider-specific request/response mapping
→ bounded application timeout/retry policy
→ existing Identity/Evidence pipeline

DaData's `find-party` endpoint is an identifier lookup/enrichment capability, not a generic region/industry discovery source. It must not be forced into the Phase 2 SearchProvider contract.

The adapter must not write canonical business state directly.

## Retry and timeout

The API is read-only, so external-effect duplication is not the blocking concern. The reliability concern is quota amplification and repeated provider load.

Therefore:
- retry only bounded transient classes;
- maximum attempts are application-configured;
- use exponential backoff with jitter;
- never retry authentication, validation, method or quota exhaustion errors;
- do not assume an undocumented Retry-After header;
- use an explicit application timeout;
- preserve SOURCE_UNAVAILABLE when the boundary cannot safely obtain a result.

This mirrors mature remote-call practice: retries belong to the reliability layer and are bounded rather than hidden inside arbitrary provider adapters.

## Required implementation before activation

1. provider adapter behind the generic SearchProvider;
2. deterministic request/response fixtures;
3. success, no-match, validation, auth, quota/rate-limit, 5xx and timeout failure tests;
4. application budget accounting;
5. correlation and redacted observability;
6. secret/configuration boundary;
7. kill-switch;
8. rollback without schema mutation;
9. full release-gate CI.

## Explicit non-goals

- no automatic qualification;
- no reliability-based global ranking;
- no canonical truth promotion;
- no fallback to FNS;
- no new DB schema;
- no kernel changes;
- no credentials in Git;
- no live-provider execution from CI.

## Exit criteria

Phase 2-H can move to controlled activation only when all implementation, negative-path, integration, security, recovery/rollback, observability and seven-job release-gate checks are green and the operator explicitly authorizes the live boundary.

## Mature-system correspondence

The design intentionally follows established patterns:
- idempotency and safe repeat semantics from production APIs such as Stripe;
- durable, bounded retry/timeout separation from workflow systems such as Temporal;
- exponential backoff with jitter from AWS reliability guidance;
- explicit run/input/output provenance from lineage systems such as OpenLineage.

These are pattern correspondences, not a reason to copy their subsystem breadth.

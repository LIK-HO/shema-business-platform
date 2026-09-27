# Phase 2-G — First Source Selection and Evidence Capture

## Status

Phase 2-G is **IN PROGRESS**: one registry-declared source is selected, authoritative evidence is captured, and activation remains blocked.

## Selected source

**FNS Transparent Business** (`fns_transparent_business`)

The source was selected because it is already declared in the machine-readable registry as an authoritative official-registry source and it is already used by the existing Phase 1-A manual counterparty-check vertical slice. This preserves the existing Identity/Evidence boundary instead of introducing a new source of truth.

## Evidence captured

The authoritative evidence record is:

`architecture/fns_transparent_business_evidence_2026_09_27.json`

The source-specific adapter boundary is:

`architecture/fns_transparent_business_adapter_contract.json`

The evidence establishes the public FNS service, its official domain, manual operator access, published availability/data-refresh facts, and the existence of an open-data context.

## Explicit evidence gaps

The checked authoritative FNS artifacts do **not** establish a machine-readable automation contract for:
- provider-side rate limits;
- provider-side timeout semantics;
- provider machine-error codes;
- provider-side idempotency or reconciliation for write effects.

These gaps are not filled by inference.

Because the registry and Phase 2-F readiness contract require authoritative provider evidence before automation, the source remains **BLOCKED for live or automated activation**.

## Safe adapter boundary

The approved boundary for this phase is observation intake:

operator lookup → structured observation → existing Identity/Evidence contracts

No network call is performed by the repository code. No background polling, scraping, retry, fallback, ranking, qualification or new persistence authority is introduced.

## Failure semantics

- no match in an operator lookup → `SEARCHED_NOT_FOUND`;
- source unavailable → `SOURCE_UNAVAILABLE`;
- operator timeout/interrupted access → `SOURCE_UNAVAILABLE`;
- contradictory identity material → quarantine/manual review;
- missing freshness/provenance → reject the observation as incomplete rather than silently promoting it to truth.

## Exit evidence for this sub-boundary

- exactly one source selected from the registry;
- authoritative evidence record committed;
- source-specific adapter contract committed;
- deterministic fixture tests committed;
- live provider traffic remains disabled;
- activation decision remains explicitly blocked until missing provider automation evidence is independently established.

## Non-goals

- automated FNS traffic;
- scraping;
- automatic retry/fallback;
- live activation;
- new database schema;
- new canonical identity semantics;
- ranking authority;
- automatic qualification;
- MAX activation;
- frozen-kernel change.

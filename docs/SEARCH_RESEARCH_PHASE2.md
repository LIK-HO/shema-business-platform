# Phase 2-A — Search Run Integrity Boundary

## Status

Phase 2-A is CLOSED / VERIFIED. Full release-gate CI #1316 passed on 2026-09-27. It does not activate external network execution and does not add persistence.

## Purpose

Establish the smallest reusable search-run contract before broader multi-source orchestration.

The slice is:

operator criteria → ordered sources → bounded execution → explicit completeness → canonical candidate normalization → measurable search quality

## Owned invariants

- SearchPlan is versioned and reproducible.
- Source order is deterministic and visible.
- Every planned source ends in an explicit attempt state when the run closes: SEARCHED, SEARCHED_NOT_FOUND, SOURCE_UNAVAILABLE, or BUDGET_LIMITED.
- Run-level completeness distinguishes NOT_SEARCHED, SEARCHED_NOT_FOUND, SOURCE_UNAVAILABLE, BUDGET_LIMITED, and COMPLETE.
- Source budgets are bounded before provider calls.
- No global ranking score is calculated or persisted.
- Candidate normalization/deduplication uses the existing canonical search contract.
- Search quality is measured separately from identity resolution and research evidence.

## Dependencies

- Existing domain.search.SearchService remains the canonical candidate-normalization primitive.
- Existing identity and evidence contracts are not changed.
- Existing Phase 1-B source registry and benchmark remain prerequisites for later source expansion.
- PostgreSQL remains the canonical transactional authority; this slice has no persistence authority.

## Failure behavior

- an explicitly unavailable source becomes SOURCE_UNAVAILABLE;
- a source not executed because a budget is exhausted becomes BUDGET_LIMITED;
- an empty successful source is SEARCHED_NOT_FOUND;
- no configured sources is NOT_SEARCHED;
- unexpected provider or programming exceptions are not silently converted into data states.

## Security / recovery boundary

No network activation, external effect, migration, retry workflow, or new system of record is introduced here.
No automatic qualification or identity promotion is performed.

## Measurement

The pilot exposes deterministic precision, recall, and source coverage metrics. These are benchmark measurements, not production SLOs.

## Explicit non-goals

- mass source integration;
- source-specific ranking authority;
- opaque scoring;
- automatic qualification;
- graph pivots;
- deep research routing;
- monitoring/revalidation;
- MAX/provider activation;
- new database schema;
- frozen-kernel semantic changes.

## Verification

CI #1316 (run id 36304414654) passed all seven release-gate jobs on HEAD af813ff79802aa358eafcb68586d3bf0b105aa7d. Phase 2-A is therefore CLOSED / VERIFIED.

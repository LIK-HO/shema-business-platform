# Phase 2-C — Registry-Backed Operator Search Composition

## Status

Phase 2-C is CLOSED / VERIFIED. It composes the verified Phase 2-A search runner and Phase 2-B registry planner behind the existing canonical /v1/search application boundary.

## Boundary

operator request → SearchCriteria → registry-backed plan → injected non-network adapters → bounded SearchRun → canonical SearchResponse

## Owned invariants

- existing /v1/search remains the single application edge;
- registry source IDs are validated before execution;
- source order remains explicit;
- search completeness is returned explicitly;
- source provenance/reliability metadata is operator-visible;
- provider network execution is not activated by this composition;
- no ranking authority or automatic qualification is introduced;
- candidate normalization continues to use the existing canonical SearchService;
- existing clients remain valid when sourceIds and budget fields are omitted.

## Dependencies

- Phase 2-A SearchRunService;
- Phase 2-B RegistryBackedSearchPlanner;
- Phase 1-B intelligence source registry;
- existing APIApplication and canonical /v1/search route;
- no persistence authority.

## Failure behavior

- unknown source ID → registry validation error;
- missing configured adapter → bounded application error;
- unavailable source → SOURCE_UNAVAILABLE;
- exhausted source/candidate budget → BUDGET_LIMITED;
- empty configured source set remains NOT_SEARCHED.

## Explicit non-goals

- external network activation;
- mass provider integration;
- ranking or global scoring;
- automatic qualification;
- new database schema/system of record;
- kernel semantic changes;
- MAX activation.

## Verification


Full CI #1330 (run id 36308647549) passed all seven release-gate jobs on HEAD 16c08111e025bd267787eaa5de36c4dd53f70609.

Phase 2-C is CLOSED / VERIFIED.

## Deliberate boundary stop

The verified slice composes the canonical search application edge but does not alter the existing provider-specific runtime composition. Phase 2-D is the separate boundary for wiring this capability into a generic runtime composition without activating providers.

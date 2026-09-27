# Phase 2-B — Source-Registry-Backed Search Planning

## Status

Phase 2-B is CLOSED / VERIFIED. It validated search sources against the Phase 1-B machine-readable intelligence source registry before a source entered a search plan.

## Boundary

The slice is:

operator criteria → registry validation → explicit source metadata → versioned search plan

No provider execution occurs inside this boundary.

## Owned invariants

- only declared registry source IDs may enter a plan;
- source order remains deterministic and is never reordered by reliability;
- source reliability is metadata, not a ranking score;
- lawful-access policy remains explicit;
- network execution stays disabled;
- source provenance metadata remains operator-visible;
- search budget stays independent from source reliability and claim confidence.

## Dependencies

- Phase 1-B `intelligence_source_registry_contract.json` is the machine-readable source-of-truth for allowed source metadata;
- Phase 2-A `SearchBudget` remains the canonical search budget primitive;
- canonical candidate search semantics remain in `domain.search`;
- no database or new system of record is introduced.

## Failure behavior

- unknown source ID → rejected;
- duplicate source ID → rejected;
- empty plan → rejected;
- registry network policy enabled → rejected;
- provider entry marked for network automation → rejected;
- reliability/claim-confidence separation removed → rejected.

## Explicit non-goals

- provider network execution;
- automatic source crawling;
- reliability-based ranking;
- opaque scoring;
- automatic qualification;
- new persistence authority;
- frozen-kernel semantic change;
- MAX activation.

## Verification target

Full CI/release gate must pass before Phase 2-B can be CLOSED / VERIFIED.
## Verification

Full CI #1324 (run id 36308069460) passed all seven release-gate jobs on HEAD ee549cada95a0a90a7647b2b01eec51fa0bdd9bc. The boundary is CLOSED / VERIFIED.

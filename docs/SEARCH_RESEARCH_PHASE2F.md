# Phase 2-F — First Approved Source Adapter Readiness

## Status

Phase 2-F is CLOSED / VERIFIED. It does not select or activate a live provider.

## Purpose

Establish the minimum evidence required before one registry-declared source may receive a controlled adapter implementation and an explicit activation decision.

## Readiness chain

provider selection → authoritative provider contract → lawful access → adapter contract → limits/error/provenance → kill-switch/rollback → fixture tests → observability → explicit operator authorization

## Owned invariants

- absence of a selected provider is NOT_READY;
- missing evidence is explicit and does not become approval by default;
- complete evidence produces READY_FOR_CONTROLLED_ACTIVATION only after all non-authorization evidence is present;
- even after explicit authorization, live activation remains a separate operation;
- no automatic retry or fallback is implied by readiness;
- readiness does not change ranking, qualification, identity or kernel semantics.

## Explicit non-goals

- choosing a provider by opaque scoring;
- live network execution;
- automatic provider activation;
- automatic retry/fallback;
- new persistence authority;
- kernel semantic change;
- MAX activation.

## Verification target

Full seven-job CI must pass before this readiness boundary is CLOSED / VERIFIED.

## Verification

Full CI #1343 (`36311263929`) passed all seven release-gate jobs on HEAD `9e49e79c3825703117ad6b587e9cee5160feaca9`.

Phase 2-F is CLOSED / VERIFIED.

## Next boundary

Phase 2-G — First Source Selection and Evidence Capture. No provider activation is authorized by this document.

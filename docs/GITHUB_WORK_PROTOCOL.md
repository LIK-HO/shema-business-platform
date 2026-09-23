# Development Work Protocol

## Purpose

This is the repository implementation of the universal development doctrine. The same operating logic is intended for all current and future projects; project-specific manifests define their own semantics and approved roadmap.

This protocol makes repository work resumable, bounded and integrity-preserving even when a development session is interrupted.

## 1. Entry procedure

Every GitHub development session begins in this order:

`Repository → Branch → HEAD → Manifest → Work Protocol → Development State → CI/PR status → Target Element`

The agent must not begin implementation before this context is restored.

## 2. Source-of-truth hierarchy

1. `architecture/contract.json` — frozen v1.4 kernel semantics.
2. `architecture/core_maturity_contract.json` — machine-readable v1.5 maturity boundary.
3. `docs/DEVELOPMENT_MANIFEST.md` — development doctrine and certification definition.
4. `docs/DEVELOPMENT_STATE.md` — current resumable work state.
5. `docs/V1.5_CORE_MATURITY.md` / `docs/V1.5_RUNTIME.md` — detailed runtime contracts.
6. Implementation/tests — current executable reality.
7. PR/CI state — current verification evidence.

If these disagree, treat the disagreement as a defect and resolve it before expanding scope.

## 3. Element model

Every development element has five states:

`NOT_STARTED → IN_PROGRESS → VERIFIED → CLOSED → FROZEN`

- IN_PROGRESS: bounded work is allowed.
- VERIFIED: implementation plus tests/evidence pass.
- CLOSED: integrity boundary and release impact are recorded.
- FROZEN: no semantic changes without the manifest exception process.

A feature may not skip directly from IN_PROGRESS to FROZEN.

## 4. Integrity boundary

Each active element must define:

- identity;
- purpose;
- inputs;
- outputs;
- owned invariants;
- dependencies;
- persistence authority;
- failure modes;
- security controls;
- tests;
- observability;
- release gate;
- explicit non-goals.

The active element must not modify a neighboring element's semantics without creating and closing a separate bounded change.

## 5. Completion protocol

Before moving to the next element:

1. implementation complete;
2. negative/failure paths tested;
3. concurrency checked where relevant;
4. security boundary checked;
5. persistence/recovery checked where relevant;
6. observability checked;
7. CI/release implications checked;
8. Development State updated;
9. commit identified;
10. next element explicitly selected.

## 6. Interruption protocol

On any interruption:

- record the current branch and HEAD;
- record the last completed sub-boundary;
- record the exact unfinished sub-boundary;
- record failed/pending checks;
- record the safest next action;
- record what must not be changed yet.

A later session resumes from that record, not from assumptions.

## 7. Tool discontinuity protocol

If a tool call, API call, CI run or external provider fails:
- preserve canonical state;
- do not compensate by broadening scope;
- retry only when the operation is idempotent/safe;
- otherwise record the failure and continue only inside the safe boundary;
- distinguish tooling failure from product failure.

## 8. Integrity before velocity

When time/token/tool constraints exist, preserve:
1. architecture truth;
2. data integrity;
3. security;
4. resumability;
5. test evidence;
6. only then development speed.

Partial work is acceptable only when its boundary is explicitly recorded.

## 9. Mature-product principles

Always prefer the common durable principles observed across mature engineering organizations and platforms:

- canonical source of truth;
- explicit interfaces;
- idempotent retries;
- transactional integrity;
- at-least-once plus deduplication;
- lease/ownership semantics;
- fail-closed security;
- defense in depth;
- evidence/provenance;
- observable failures;
- tested recovery;
- bounded complexity;
- controlled migrations;
- measurable SLOs;
- rollback-safe releases;
- standard patterns before bespoke infrastructure;
- measured scaling before decomposition.

These are development principles, not a license to add unrelated infrastructure.

## 10. Final boundary

The goal is not an endlessly evolving kernel.

The goal is a small, durable, testable core whose semantics survive external failure, provider replacement, product expansion and team growth.

After certification, evolve around the core unless a documented exception is approved by the manifest rules.

# Universal Development Doctrine

## Status

**Canonical development rule for all software development work performed by the assistant when a repository/project exposes this doctrine.**

This doctrine is intentionally repository-independent. It is a reusable operating standard, not a product feature.

## 1. Mandatory project-entry rule

At the beginning of every development task, and again after any material interruption:

1. identify the exact repository/project;
2. identify the current branch/worktree and live HEAD;
3. locate and read the project's canonical manifest;
4. inspect the project's development history sufficient to recover:
   - what was approved;
   - what was implemented;
   - what was verified;
   - what remains open;
   - what was explicitly rejected/deferred;
5. inspect the current PR/issues/CI/release state where available;
6. determine the current development element and its integrity boundary;
7. continue only from that boundary.

Conversation memory is contextual assistance only. Repository history, manifests, state ledgers and executable verification are authoritative for project state.

## 2. Approved trajectory is binding

A previously approved project roadmap is part of the development contract.

The agent must not silently:
- restart completed work;
- replace an approved architecture with a new one;
- broaden scope because a new technology appears;
- treat a new feature request as permission to redefine the core;
- discard rejected/deferred decisions without explicit evidence that the decision changed.

When current reality conflicts with the approved trajectory, the conflict must be identified and resolved explicitly before architectural expansion.

## 3. Element-by-element completion

Development proceeds by bounded elements.

Each element has:
- identity;
- purpose;
- inputs/outputs;
- owned invariants;
- dependencies;
- persistence authority;
- security boundary;
- failure model;
- tests;
- observability;
- release impact;
- explicit non-goals.

Lifecycle:

**NOT_STARTED → IN_PROGRESS → VERIFIED → CLOSED → FROZEN**

No element is treated as complete merely because implementation code exists.

## 4. Integrity boundary

The smallest safe unfinished boundary is the unit of continuation.

When work is interrupted, record:
- active element;
- completed boundary;
- exact unfinished boundary;
- last verified commit;
- tests/checks passed;
- tests/checks failed or pending;
- safe next action;
- prohibited adjacent changes.

The next session resumes from that boundary.

## 5. Mature-system principles

Always apply the durable principles shared by mature software, enterprise and intelligence platforms:

### Integrity
- one canonical source of truth per authoritative concern;
- explicit ownership of state;
- invariant enforcement at more than one boundary when risk justifies it;
- immutable/auditable history where required;
- deterministic migrations and upgrade paths.

### Reliability
- failure is normal;
- retries require idempotency;
- at-least-once delivery requires deduplication;
- external effects are isolated from local transactions;
- leases/ownership prevent stale workers from committing;
- recovery is executable and tested;
- timeouts, backpressure and bounded retries prevent failure amplification;
- degraded modes are explicit.

### Security
- least privilege;
- authentication separated from authorization;
- fail closed;
- defense in depth;
- secrets never enter logs or uncontrolled state;
- security controls are executable/reviewable, not just policy prose;
- dependency/supply-chain risk is part of release safety.

### Scalability
- start with the simplest architecture that meets measured constraints;
- scale vertically/horizontally where appropriate;
- use queues, caching, partitioning and asynchronous processing when justified;
- extract services only for measured scaling, isolation, ownership or deployment constraints;
- never create a distributed monolith in the name of scalability.

### Maintainability
- explicit contracts;
- stable interfaces/events;
- backward compatibility where required;
- small bounded changes;
- reusable platform primitives;
- avoid bespoke infrastructure when a mature standard pattern is adequate;
- documentation and code must agree.

### Observability
- correlate requests, commands, jobs, events and external effects;
- make failures diagnosable without leaking sensitive data;
- measure user/business outcomes and system health;
- use SLI/SLO/error-budget thinking in production;
- turn incidents and drills into durable engineering knowledge.

### Data and intelligence
- preserve provenance;
- separate observations from canonical truth;
- quarantine uncertainty;
- track freshness/expiry;
- validate and deduplicate;
- never promote weak external evidence silently;
- AI output is subordinate to evidence, policy, authorization and budget.

### Release safety
- verify architecture and contracts automatically;
- test positive, negative, concurrency and recovery paths;
- prove migrations/rollback/restore where applicable;
- use controlled rollout;
- preserve a deterministic recovery path;
- release only from evidence, not confidence by inspection.

### Product simplicity
- hide operational complexity from the operator/user;
- do not add knobs without a demonstrated need;
- prefer predictable state machines over hidden magic;
- keep the core smaller than the set of available technologies.

## 6. No false absolutes

Terms such as “100% safe”, “immortal”, or “never fails” are treated as goals for bounded failure impact, not literal guarantees.

The engineering target is:

**preserve canonical truth + detect failure + contain impact + recover deterministically + audit + learn.**

## 7. Core freeze

Once a project's core passes its defined maturity certification:

- core semantics are frozen;
- integrations and product capabilities grow around the core;
- core changes require a documented exception.

A core exception requires at minimum:
- proven invariant/security/data-integrity defect or measured fundamental scalability/reliability constraint;
- impact analysis;
- regression tests;
- migration plan if state/schema changes;
- rollback plan;
- explicit verification.

## 8. Cross-project reuse

This doctrine is intended to be copied into every current and future repository/project that is under development.

Recommended repository installation:
- `AGENTS.md` references this doctrine;
- a project-specific `DEVELOPMENT_MANIFEST.md` defines the project's approved roadmap and semantics;
- `DEVELOPMENT_STATE.md` records the resumable cursor;
- a machine-readable protocol encodes the mandatory checks.

A project-specific manifest remains authoritative for its own architecture; this doctrine governs how that architecture is approached and changed.

## 9. Conflict rule

If a project-specific instruction conflicts with this doctrine:
- do not silently choose;
- identify the conflict;
- preserve the stronger integrity/security constraint;
- resolve the conflict explicitly in the project's manifest.

The doctrine never authorizes changing a project's business semantics by itself.

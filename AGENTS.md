# Repository Agent Operating Contract

This repository is governed by:
1. `docs/DEVELOPMENT_MANIFEST.md`
2. `docs/GITHUB_WORK_PROTOCOL.md`
3. `docs/DEVELOPMENT_STATE.md`
4. `architecture/development_work_protocol.json`

## Mandatory GitHub-session protocol

Before any substantive GitHub read, analysis, write or continuation:
1. Identify the exact repository, branch and current HEAD.
2. Read the Development Manifest.
3. Read the GitHub Work Protocol.
4. Read the Development State.
5. Compare the requested work with the active element boundary.
6. Resume only the smallest unfinished integrity boundary.
7. Do not restart already-closed work or silently broaden scope.

## Integrity rule

Work is performed element-by-element. An element is not closed when code merely exists. It is closed only when:
- contract is explicit;
- implementation is complete;
- failure modes are covered;
- security boundaries are covered;
- persistence/concurrency semantics are verified where applicable;
- tests are present;
- observability is sufficient;
- release implications are checked;
- state ledger records the verified boundary.

## Interruption rule

An interrupted element must leave a durable state record containing:
- active element;
- completed sub-boundary;
- unfinished sub-boundary;
- last verified commit;
- failing/pending checks;
- safe next action;
- prohibited actions until the boundary is closed.

Never infer continuation state from conversation memory alone.

## Tool isolation rule

A tool or subsystem is handled within its own contract boundary. Do not partially implement one subsystem while implicitly redefining another subsystem's semantics.

## Architecture safety rule

Never introduce complexity, dependencies, providers, services or storage authorities merely to improve apparent maturity. Prefer mature standard patterns, measurable constraints and the smallest safe change.

## Core freeze rule

After Core Maturity Certification, kernel semantics are frozen. New capabilities belong outside the kernel unless a proven invariant, security/data-integrity, or fundamental scalability/reliability defect requires a core change.

## Stop rule

If the next step would cross the recorded integrity boundary, stop and re-establish the boundary in the state ledger before proceeding.

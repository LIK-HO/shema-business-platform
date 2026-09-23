# v1.5 Core Semantic Freeze

## Final boundary

The v1.5 release candidate preserves the frozen v1.4 business/domain kernel and adds only verified runtime and maturity controls around it.

The semantic freeze takes effect only after the final release-candidate CI is green.

## Frozen after certification

The following remain authoritative and are not to be redefined for ordinary product work:

- v1.4 architecture/domain semantics;
- PostgreSQL as canonical transactional authority;
- identity/evidence/idempotency/audit/outbox authority boundaries;
- critical workflow transactional semantics;
- durable job lease and retry semantics;
- external-effect reservation and idempotency semantics;
- canonical API business semantics.

## Post-certification rule

New product capabilities belong outside the kernel: application extensions, adapters, integrations, clients and experience layers.

A core change is exceptional and requires evidence of at least one of:

- a proven invariant defect;
- a security defect;
- a data-integrity defect;
- a fundamental reliability/scalability boundary;
- a changed fundamental business invariant.

An exceptional core change also requires regression tests, impact analysis, migration planning where applicable and a rollback plan.

## Release boundary

This document does not authorize production deployment or merge. It defines the architectural stop line and change policy for the certified core.

# Capacity / Overload Baseline — v1.5

This is the minimum bounded operational baseline required by the maturity manifest before the release candidate.

It does **not** claim a production throughput number. It proves that the existing runtime has bounded behavior under the principal overload mechanisms already present, without changing frozen v1.4 semantics.

| Boundary | Existing control | Proof |
|---|---|---|
| Concurrent critical commands | PostgreSQL uniqueness + transactional idempotency | 8-way concurrent critical-create integration proof |
| Worker saturation | lease ownership, reclaim, bounded retry | PostgreSQL job reclaim test |
| Retry storm | max 5 attempts, exponential backoff capped at 60s | RetryPolicy |
| Queue backlog | bounded outbox claim/dispatch batch, default 100 | outbox dispatcher limit test |
| DB contention | transactional uniqueness / row-ownership semantics | concurrent idempotency integration proof |
| Rate limiting | deliberately outside frozen kernel authority | edge/product concern; no distributed limiter added without measured need |
| Graceful degradation | canonical API returns bounded 503 when application services are unavailable | API runtime test |

## Important boundary

The core does not pretend that a single-process or in-process limiter is a production-grade distributed rate limiter. Introducing one into the kernel without a measured requirement would add state, semantics and failure modes without evidence.

Ingress rate limiting belongs at the deployment/API-edge boundary when a real traffic profile establishes that requirement.

## Acceptance

B9 can close when:

- concurrent critical commands are proven to converge safely;
- workers remain lease-owned under reclaim/pressure;
- retry behavior is bounded;
- queue work is batch-bounded;
- database contention does not create duplicate canonical business state;
- graceful degradation is explicit;
- no capacity test requires a kernel semantic change.

This is a behavioral safety baseline, not a production capacity guarantee.

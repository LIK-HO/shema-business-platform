# Intelligence Provider Resource / Cost Guard

## Purpose

P8 makes the existing research resource budget a hard pre-I/O control.

The guard does not create a second economic ledger. It evaluates the existing `ResearchBudget` together with `ProviderCapability` before a provider call is made.

## Pre-I/O controls

Before `provider.research(...)` the gateway verifies:

- remaining provider-call budget;
- remaining source budget;
- estimated provider cost;
- estimated token consumption;
- estimated latency/time budget;
- provider request-rate allowance.

A rejected provider is never called.

When the provider-call or source budget is exhausted, the current research operation stops. When a particular provider exceeds cost/token/time/rate constraints, that provider is skipped and the waterfall may continue with another eligible provider.

## Rate limiting

Rate limiting is process-local and keyed by provider identifier. The provider's declared `max_requests_per_second` is the ceiling.

The guard rejects a call when the minimum interval since the previous call has not elapsed. It does not sleep inside the application research path and therefore cannot hide resource pressure.

## Post-call accounting

The existing gateway continues to account actual result cost, tokens, latency and source usage against the same `ResearchBudget`.

The guard is therefore a pre-I/O admission control layer, not a replacement for actual usage accounting.

## Boundary

P8 does not:

- create durable economic records;
- modify pricing or business economics;
- change provider routing semantics;
- make provider cost authoritative;
- add a global distributed rate limiter;
- automatically activate providers.

Future distributed quota enforcement, when necessary, remains an operational deployment concern outside the frozen kernel.

# Productization Hardening Review

## Decision

The OpenCorporates hardening slice is complete. P1–P21 now cover the concrete provider's resource, transport, failure, provenance, observation-integrity and duplication boundaries. The review found no additional control with sufficiently distinct risk reduction to justify another provider-specific micro-boundary.

## Verified controls

| Area | Control |
|---|---|
| Input | Query and encoded request envelope bounds; fail-closed before I/O |
| Response | Bounded body read; non-2xx failure before JSON materialization |
| Execution | Timeout, deadline, rate-limit wait budget, provider resource/cost guard |
| Activation | Explicit provider activation/configuration; health/readiness/probes |
| Provenance | Exact HTTPS host; company path; canonicalization; no query/fragment/non-default port |
| Observation | Field length/type bounds; payload/provenance identity consistency |
| Duplication | One observation per canonical provenance reference; first valid observation wins |
| Core boundary | No frozen-kernel semantic changes |

## Exit criterion

Further OpenCorporates-specific controls should only be added when a new measurable production risk appears. Otherwise the bounded-complexity rule requires moving to the next product surface.

## Next surface

P23 targets the real MAX outbound communication adapter. The existing MAX safety assessment is fail-closed: live activation requires proven provider-side idempotency or deterministic reconciliation for crash-after-external-effect recovery. The next implementation must prove those semantics or preserve quarantine; it must not assume them.

# SLO / Error-Budget Baseline — v1.5

This is the initial operational baseline required by the maturity manifest. It defines measurable objectives without changing frozen v1.4 business or domain semantics.

All SLOs use a rolling 30-day window. An SLI is calculated as: good events / eligible events.

| SLI | Initial target | Measurement source | Objective |
|---|---:|---|---|
| API availability | 99.5% | HTTP telemetry | <500 responses are failures |
| Critical mutation success | 99.9% | workflow/audit outcome | critical mutations converge without terminal system failure |
| Job recovery | 99.0% | durable job state | retryable failures converge within recovery deadline |
| Outbox lag | 99.0% | outbox timestamps | eligible events delivered within 60s |
| External-effect completion | 99.0% | commercial send state | reserved effects converge within 5m |
| API latency | 99.0% | HTTP telemetry | requests complete within 1000ms |

## Error budgets

Error budget = 1 - target. Initial monthly budgets: API availability 0.5%; critical mutation success 0.1%; job recovery 1.0%; outbox lag 1.0%; external-effect completion 1.0%; API latency 1.0%.

Below 50% remaining: reliability review before non-reliability core changes. Below 20%: pause non-essential reliability-neutral releases until recovery.

## Measurement boundaries

- PostgreSQL remains canonical for business state.
- Telemetry is observational and non-authoritative.
- Request bodies and authorization headers are excluded from SLI sources.
- Missing telemetry is not a successful event.
- External-provider outages count against the relevant accepted-operation objective.

## Certification status

This contract is executablely validated for structure and policy. It is a baseline, not a measured production SLO report. Real production measurement and alerting remain an operations/product concern after core certification.
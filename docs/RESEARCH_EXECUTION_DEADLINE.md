# Research Execution Deadline

P10 binds the existing operation-scoped research time budget to actual external provider execution.

- `ResearchBudget.time_budget_seconds` is propagated as the remaining execution timeout for each provider call.
- A provider cannot receive a timeout greater than the remaining research time budget.
- The provider's own configured timeout remains an independent hard bound; effective timeout is the smaller of the two.
- When no research time remains, the gateway skips further provider execution.
- Non-positive explicit provider deadline overrides fail closed.
- No automatic retry, scheduler, durable-job semantics, global limiter, billing ledger or kernel change is introduced.
- The control is operational and application/provider-specific; it is not canonical business state.

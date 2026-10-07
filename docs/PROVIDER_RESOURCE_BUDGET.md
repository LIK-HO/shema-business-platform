# Provider Resource / Cost Guard

P8 bounds external intelligence consumption at the operation boundary.

- A caller supplies an explicit `ProviderBudget`.
- A call is reserved before external I/O.
- Exhaustion raises `ProviderBudgetExceeded` before the requester is invoked.
- The guard is process-local and operation-scoped.
- It is not canonical economic state and does not persist spend or provider billing data.
- Provider-specific request-rate controls remain with the existing adapter/provider configuration.
- No automatic retry, scheduler, billing ledger or global distributed limiter is introduced by this boundary.

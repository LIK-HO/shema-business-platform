# Provider Operation Execution Policy

P9 bounds the execution envelope of external provider operations.

- Provider timeout must be explicit and positive.
- Provider timeout is hard-bounded at 30 seconds by the current contract.
- The bounded timeout is passed directly to the external requester.
- Provider failures remain fail-closed; this boundary does not introduce automatic retries.
- No scheduler, durable job semantics, global limiter, billing ledger or kernel change is introduced.
- The policy is operational and provider-specific; it does not become canonical business state.

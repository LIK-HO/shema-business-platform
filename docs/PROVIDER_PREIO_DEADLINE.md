# Provider Pre-I/O Deadline

P12 completes the provider execution envelope by including provider-local rate-limit wait in the same execution deadline.

- The provider derives a monotonic deadline from its effective timeout.
- Rate-limit sleep is permitted only when it fits inside the remaining deadline.
- If the pre-I/O wait would consume the remaining deadline, the operation fails closed without external I/O.
- After any rate-limit wait, the HTTP requester receives only the remaining timeout.
- No retry scheduler, durable-job semantics, global limiter, billing ledger or kernel change is introduced.
- The control is operational and provider-specific.

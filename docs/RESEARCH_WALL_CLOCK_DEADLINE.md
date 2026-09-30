# Research Wall-Clock Deadline

P11 makes the research operation deadline authoritative from the local monotonic clock.

- The operation captures a monotonic deadline at the start of the provider waterfall.
- Before each provider call, the gateway computes the actual remaining wall-clock budget.
- Provider execution receives that remaining budget as its timeout cap.
- Provider-reported `latency_seconds` remains usage metadata and is not trusted to extend the operation deadline.
- When the wall-clock budget is exhausted, no further provider is executed.
- No automatic retry, scheduler, durable-job semantics, global limiter, billing ledger or kernel change is introduced.
- The control remains outside canonical business state.

# Provider Response Size Limit

P13 bounds the size of an external intelligence-provider response.

Purpose:
- prevent an external provider from returning an unbounded payload;
- enforce the limit at the transport boundary and again at the adapter boundary;
- fail closed before JSON materialization when the configured limit is exceeded.

Contract:
- default response limit is 1 MiB (1,048,576 bytes);
- configurable limit is capped at 4 MiB (4,194,304 bytes);
- the transport reads at most limit + 1 bytes;
- the adapter rejects oversized injected/custom responses before JSON parsing;
- readiness checks use the same transport response bound;
- no provider response body is persisted or emitted as telemetry;
- no kernel, retry scheduler, durable job, global limiter, billing ledger or deployment semantic is introduced.

Runtime configuration:
OPENCORPORATES_MAX_RESPONSE_BYTES

The value is parsed as an integer and must be positive and no greater than 4,194,304.

The control is provider-specific and operational. It protects resource bounds; it does not change the canonical business-truth model.

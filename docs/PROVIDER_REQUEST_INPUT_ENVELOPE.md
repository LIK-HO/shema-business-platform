# Provider Request-Input Envelope

P14 bounds the input side of the OpenCorporates provider operation.

Purpose:
- prevent an unbounded provider query from reaching external I/O;
- bound the complete encoded GET request envelope, including the endpoint and query parameters;
- fail closed before rate-limit waiting and before transport I/O.

Contract:
- default query limit is 1,024 Unicode characters;
- configurable query limit is capped at 4,096 characters;
- default encoded request-URL limit is 8,192 bytes;
- configurable request-URL limit is capped at 16,384 bytes;
- both checks happen before provider throttling;
- the HTTP transport repeats the request-URL check immediately before urlopen;
- the existing three-argument requester seam is preserved;
- readiness probes use the same request-envelope bound;
- no provider response body is persisted or emitted as telemetry;
- the limits are platform operational guards, not claims about an upstream OpenCorporates hard limit.

OpenCorporates documents the company-search endpoint as a GET request with the search term supplied in q, and documents pagination and account-dependent usage limits. It does not publish a fixed maximum for q in the current API reference, so the above values are intentionally platform-side resource bounds rather than upstream contract values.

Runtime configuration:
- OPENCORPORATES_MAX_QUERY_CHARS
- OPENCORPORATES_MAX_REQUEST_URL_BYTES

No kernel, retry scheduler, durable job, global limiter, billing ledger or deployment semantics are introduced.

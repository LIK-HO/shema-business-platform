# Provider Failure-Path Materialization Guard

P15 makes the concrete OpenCorporates adapter reject non-success HTTP responses before JSON materialization.

Purpose:
- keep provider error responses out of the business-payload parser;
- preserve bounded response-size enforcement;
- prevent malformed or unexpected error bodies from being interpreted as provider result structures.

Contract:
- response size is still bounded before any parsing;
- any non-200 HTTP status fails immediately with the existing ConnectionError contract;
- only HTTP 200 responses are JSON-materialized into ProviderResult;
- no provider error body is persisted or emitted as telemetry;
- no automatic retry, retry scheduler, durable job, billing ledger, or kernel semantic is introduced.

No upstream provider semantic is inferred beyond the documented HTTP success path.

# OpenCorporates Provider

## Purpose

This adapter is the first concrete intelligence provider in the v1.5 productization boundary. It converts OpenCorporates company-search observations into the existing `ProviderResult` contract; it does not write canonical identity, order, economics, or other business state directly.

## Verified external contract

The current OpenCorporates API documentation states that:

- the REST API is versioned and the documentation currently covers API reference version 0.4.8;
- API access requires an API key/token;
- the HTTPS endpoint should be used;
- company search is available at `/v0.4/companies/search`;
- results expose company URLs and source/provenance information;
- API usage limits depend on the account type/plan.

The adapter therefore fixes the API version in the endpoint, uses HTTPS, requires an API token from environment configuration, and refuses to materialize claims that do not have an HTTPS OpenCorporates source URL.

External reference:
https://api.opencorporates.com/documentation/API-Reference

## Runtime configuration

Required:

`OPENCORPORATES_API_TOKEN`

Optional:

`OPENCORPORATES_API_VERSION` (default `0.4`)
`OPENCORPORATES_TIMEOUT_SECONDS` (default `5`)
`OPENCORPORATES_COST_PER_CALL` (default `0`)
`OPENCORPORATES_MAX_REQUESTS_PER_SECOND` (default `1`)
`OPENCORPORATES_COVERAGE` (default `company,logistics,construction,trade`)
`OPENCORPORATES_CONFIDENCE` (default `0.8`)

The confidence value is an application calibration parameter, not a claim made by OpenCorporates.

## Safety boundary

The adapter:

- performs only external reads;
- never becomes a source of canonical identity truth by itself;
- emits claims only with a provider URL;
- caps each call at 50 results;
- enforces a local inter-request throttle;
- fails on non-200 HTTP responses and malformed JSON;
- does not auto-activate in production;
- preserves the existing `IntelligenceService` transaction boundary: provider I/O occurs before evidence persistence.

## Production activation gate

Before production activation, the deployment layer must provide a secret API token and an explicit configuration snapshot. Provider availability and account limits must be monitored; the adapter must not be treated as an authoritative registry.

The next provider should reuse the same `ResearchProvider` / `ProviderCapability` boundary rather than adding provider-specific semantics to the kernel.

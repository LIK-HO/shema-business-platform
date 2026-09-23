# Explicit Provider Readiness Probes

## Purpose

P7 connects the P6 health registry to provider-specific transport probes.

A probe is an explicit operational action. The `/health/ready` endpoint never runs probes implicitly.

## OpenCorporates probe

The OpenCorporates probe:

- uses the existing versioned company-search HTTPS endpoint;
- sends a dedicated non-business probe query;
- requests at most one result;
- treats only the HTTP status as probe evidence;
- never parses, persists or emits the response body;
- maps non-200 responses to bounded error codes such as `HTTP_401` or `HTTP_429`;
- maps transport failures to `CONNECTION_ERROR`.

The probe consumes one provider API request when explicitly executed. It is therefore a controlled operational action, not part of every health check.

## Health and telemetry

`ProviderProbeRunner`:

1. verifies the provider is registered;
2. skips disabled providers;
3. executes the explicit probe;
4. updates only `ProviderHealthRegistry`;
5. emits existing non-authoritative telemetry using only provider/status/error-code metadata.

No provider response payload, API token, request body, business claim or canonical state enters the resulting health or telemetry records.

## Operational boundary

This layer does not:

- automatically schedule probes;
- add a durable probe-result store;
- mutate identity/order/economics state;
- alter research-routing policy;
- activate providers in production.

Scheduling or deployment orchestration remains a separate future boundary.

# Provider Health / Readiness

## Purpose

P6 provides a safe operational health surface for external providers.

The registry stores only:

- provider identifier;
- enabled/configured flags;
- last reachability state;
- last check timestamp;
- bounded error code.

It never stores API secrets, request bodies, provider response payloads or business claims.

## HTTP surface

`GET /health/ready` is intentionally unauthenticated so an orchestrator can use it without application credentials.

It returns HTTP 200 when every enabled provider is configured and currently reachable. It returns HTTP 503 when an enabled provider is unconfigured, has unknown reachability, or is currently unreachable.

The response is operational metadata only and does not represent canonical business truth.

## Failure model

A provider can be:

- disabled: readiness does not depend on it;
- enabled but unconfigured: not ready;
- enabled and configured but not yet checked: not ready;
- enabled and reachable: ready;
- enabled and unreachable: not ready, with only a bounded error code exposed.

The registry is process-local. Durable historical observability remains the responsibility of the existing telemetry/operational stack; this boundary deliberately avoids introducing a new system of record.

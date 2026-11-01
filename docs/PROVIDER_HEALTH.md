# Provider Health / Readiness

## Purpose

P6 provides a safe operational health surface for external providers.

The process-local registry stores only (internal operational state):

- provider identifier;
- enabled/configured flags;
- last reachability state;
- last check timestamp;
- bounded error code.

It never stores API secrets, request bodies, provider response payloads or business claims.

## HTTP surface

`GET /health/ready` is intentionally unauthenticated so an orchestrator can use it without application credentials.

The endpoint returns only `{"ready": true|false}`; it does not expose provider identifiers, configuration flags, reachability details, timestamps or error codes. Internal provider state and error codes remain process-local and are not returned over this unauthenticated endpoint.

It returns HTTP 200 only when at least one runtime service has been composed and every enabled registered provider is configured and currently reachable. It returns HTTP 503 when no runtime service is composed, or an enabled provider is unconfigured, has unknown reachability, or is currently unreachable.

This is a narrow process/provider readiness signal, not full production readiness: it does not verify PostgreSQL connectivity, durable worker execution, external routing, backups, monitoring, or deployment/rollback capability. Those must be verified by the target environment and production acceptance gates. The endpoint does not represent canonical business truth.

## Failure model

A provider can be:

- disabled: readiness does not depend on it;
- enabled but unconfigured: not ready;
- enabled and configured but not yet checked: not ready;
- enabled and reachable: ready;
- enabled and unreachable: not ready; a bounded error code is retained internally but not exposed by the HTTP response.

The registry is process-local. Durable historical observability remains the responsibility of the existing telemetry/operational stack; this boundary deliberately avoids introducing a new system of record.

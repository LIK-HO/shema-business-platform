# Controlled Provider Activation — 2026-09-27

## Boundary

Phase 2-H is extended with a separate controlled activation operation for
dadata_organization_api.

The operation is not provider discovery. It controls only whether an already
verified provider binding may be used for counterparty lookup.

## Required sequence

1. Authenticate the operator through the existing API authentication boundary.
2. Authorize intelligence.provider.activate or intelligence.provider.rollback.
3. Require explicit operator confirmation.
4. Verify the complete Phase 2-H readiness evidence.
5. Verify provider execution configuration and secret presence inside the
   adapter boundary only.
6. Activate a process-local provider binding.
7. Execute lookup only through the gated binding.
8. Emit redacted activation/rollback telemetry.
9. Roll back by disabling the binding; historical evidence is not deleted.

## Explicit safety properties

- Construction and application startup do not activate DaData traffic.
- The default configuration remains enabled=False.
- Readiness is supplied as a verification artifact; the operation does not
  pretend that source code can prove a current CI release state.
- No API key is persisted in activation state or telemetry.
- No automatic activation or provider fallback exists.
- Rollback is fail-closed and reversible without schema rewrite.
- The provider remains secondary evidence and cannot become canonical truth.

## Deliberate non-goals

This boundary does not:
- turn on live DaData in this repository;
- invent missing FNS automation evidence;
- add database schema;
- modify the frozen v1.4 kernel;
- create a second identity truth path;
- implement multi-provider fallback;
- grant MAX activation.

## Verification target

The element is closed only after the new control-plane tests and the full
seven-job release gate are GREEN on the final synchronized HEAD.

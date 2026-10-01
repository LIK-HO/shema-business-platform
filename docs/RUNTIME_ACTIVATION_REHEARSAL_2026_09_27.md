# Runtime Activation Rehearsal — 2026-09-27

## Boundary

The next Phase 2-H slice is a **runtime activation rehearsal**. It proves that
the verified DaData control-plane can be composed through the canonical runtime
without turning provider execution on implicitly.

## Required composition

1. Build a provider-neutral runtime assembly around the existing application/API
   composition boundary.
2. Inject an explicit DaData readiness witness; do not infer current CI state
   from source code.
3. Keep the provider configuration disabled by default.
4. Permit a deterministic fake provider only inside the rehearsal tests.
5. Expose the existing authenticated activation/rollback routes only when the
   control-plane capability is deliberately composed.
6. Prove activation requires:
   - authenticated actor;
   - dedicated activation permission;
   - explicit operator confirmation;
   - complete readiness witness;
   - enabled provider configuration.
7. Prove rollback disables the binding and blocks subsequent lookup execution.
8. Prove no real DaData network call is made by assembly, startup or tests.

## Explicit non-goals

This slice does not:
- enable live DaData;
- introduce provider fallback;
- add a database table or migration;
- change canonical Identity semantics;
- alter the frozen v1.4 kernel;
- bypass the existing manual authoritative FNS path;
- treat the readiness witness as proof of production authorization.

## Exit criteria

The runtime-composed activation/rollback path passes deterministic unit/runtime
tests and the complete seven-job release gate. The final state remains
live-provider-OFF.

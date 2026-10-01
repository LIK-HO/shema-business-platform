# P34 — GigaChat Application Composition / Activation Proof

P34 composes the verified GigaChat adapter and production gate with the existing provider-neutral AI application service.

## Execution boundary

The composition path is:

GigaChat production gate
→ scoped GigaChat provider
→ frozen AIGateway
→ provider-neutral AIExecutionService.

No new Gateway semantics are introduced.

## Activation

The composition is disabled by default. Activation is explicit and delegates to the already verified GigaChat production gate. Rollback removes the active provider from the composition.

Creating the composition or asking for its service does not activate provider traffic.

## Trust and persistence

P34 does not create a second trust system. Resource/evidence trust remains resolved by the existing application-side canonical PostgreSQL resolver when the service executes.

Canonical AIRun persistence and audit remain owned by the frozen AIGateway.

## Scope stop

P34 does not add:

- a new provider;
- OpenAI;
- local runtime or Cloud ↔ Local fallback;
- database schema/migrations;
- HTTP/application runtime wiring;
- live provider traffic.

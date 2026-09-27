# Counterparty Provider Lookup → Evidence Runtime Vertical Slice — 2026-09-27

## Boundary

The next Phase 2-H slice connects the already verified CounterpartyProviderLookupService
to the explicitly composed CounterpartyProviderRuntimeAssembly.

The runtime must expose one coherent path:

authenticated operator → explicit provider activation → provider-neutral lookup → bounded retry → Evidence intake → audit → response

The provider remains trusted_secondary; canonical Identity is never promoted
by this slice.

## Required composition

- Reuse CounterpartyProviderLookupService; do not duplicate retry or evidence logic.
- Acquire the provider only from the activated/gated runtime binding.
- Supply CounterpartyProviderEvidenceService through the existing UnitOfWork boundary.
- Keep claim confidence and evidence expiry explicit inputs; do not invent them.
- Propagate the request correlation ID into the Evidence audit record.
- Return provider observation + evidence result as a bounded operator/API result.
- Rollback must make subsequent lookup execution fail closed.

## Verification

The slice is verified only when deterministic runtime/E2E tests prove:
1. authentication and provider activation are enforced;
2. an inactive provider cannot perform lookup;
3. an activated deterministic fixture performs one lookup;
4. Evidence records are written through the existing UnitOfWork;
5. audit contains the same correlation ID;
6. canonical Identity is not created or promoted by secondary provider evidence;
7. rollback disables future lookup;
8. no real DaData network call occurs;
9. the full seven-job release gate is GREEN.

## Non-goals

- live DaData traffic;
- automatic activation;
- fallback to FNS or another provider;
- new database schema;
- alternate canonical identity authority;
- weakening the manual authoritative FNS route;
- kernel changes.

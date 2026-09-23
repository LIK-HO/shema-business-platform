# OpenCorporates Activation Boundary

## Purpose

P5 adds a controlled composition boundary around the already verified OpenCorporates provider.

Activation requires all of the following:

1. a versioned `ConfigurationSnapshot`;
2. the feature flag `intelligence.opencorporates.enabled=true`;
3. a runtime API token supplied outside the snapshot.

The configuration snapshot contains operational policy only. The API secret is never persisted in the snapshot.

## Fail-closed behavior

- feature flag absent/false: provider is not composed;
- feature flag true but API token absent: composition fails;
- invalid operational values: composition fails through `OpenCorporatesConfiguration`;
- no code path in this boundary automatically enables the provider in production.

## Separation of concerns

The factory only constructs an adapter. It does not:

- modify canonical identity state;
- write evidence;
- mutate orders/economics;
- change research-routing policy;
- activate deployment infrastructure.

The existing application/research layer remains responsible for choosing providers and persisting evidence.

## Secret handling

The versioned configuration snapshot must not contain `OPENCORPORATES_API_TOKEN` or any equivalent secret value.

A deployment system may provide the secret at runtime. This branch does not create or populate deployment secrets and does not authorize production activation.

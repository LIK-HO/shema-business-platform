# P36 — Approved AI Provider Selection

P36 adds one bounded composition-root selector for the two already approved cloud AI providers.

## Selection boundary

The selector accepts an operator/configuration value and chooses exactly one already-composed runtime:

- `yandexgpt`;
- `gigachat`.

The selected runtime is stored in an immutable assembly object.

## Safety properties

Selection:

- happens outside the HTTP request;
- does not inspect or modify frozen kernel state;
- does not activate a provider;
- performs no provider network I/O;
- does not fall back to another provider when the requested composition is absent;
- rejects any provider outside the approved allow-list.

Provider-specific production gates remain authoritative after selection. Choosing a provider is not equivalent to activating it.

## Scope stop

P36 does not add:

- a new AI provider;
- OpenAI;
- a local/self-hosted model runtime;
- Cloud ↔ Local fallback;
- provider selection fields to `POST /v1/ai/run`;
- database schema or migrations;
- frozen kernel changes;
- automatic production activation;
- live provider traffic.

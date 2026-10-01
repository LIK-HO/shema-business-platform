# P35 — GigaChat Runtime Assembly

P35 adds an explicit runtime composition root for the already verified GigaChat application composition.

## Assembly path

`compose_gigachat_runtime()`
→ `GigaChatApplicationComposition`
→ `AIExecutionService`
→ `AIOnlyAPIApplication`
→ `create_app()`

Construction remains side-effect free with respect to provider traffic.

## Activation

The runtime exposes only explicit GigaChat activation and rollback operations. Activation delegates to the already verified P33 production gate through P34 composition.

Runtime construction, application construction and HTTP app construction do not activate GigaChat.

## Boundary

P35 owns only:

- runtime dependency assembly for GigaChat;
- API application construction;
- explicit activation/rollback controls.

P35 does not add:

- provider selection in the HTTP request;
- automatic provider fallback;
- a new provider;
- local/self-hosted runtime;
- database schema or migrations;
- frozen kernel changes;
- automatic production activation;
- live provider traffic.

YandexGPT remains separately assembled by the existing P31 runtime root. A future unified operator-level composition may combine both approved providers, but that is intentionally outside P35.

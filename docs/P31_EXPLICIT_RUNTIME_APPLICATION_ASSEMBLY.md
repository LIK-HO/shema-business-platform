# P31 — Explicit Production Application Assembly

P31 adds one explicit composition root for the already verified YandexGPT application capability.

## Assembly path

`compose_yandexgpt_runtime()`
→ `YandexGPTApplicationComposition`
→ `AIExecutionService`
→ `AIOnlyAPIApplication`
→ `create_app()`

Construction does not activate the YandexGPT production gate.

## Explicit activation

The returned `YandexGPTRuntimeAssembly` exposes explicit activation and rollback methods only. A runtime operator must intentionally call activation with an operator identity and, where required, the runtime-only API key.

No module import, application construction, HTTP app creation or server startup activates provider traffic.

## Boundary

P31 owns composition only:

- dependency injection;
- application assembly;
- API application construction;
- explicit activation/rollback controls.

P31 does not add a provider, modify the kernel, change the database schema, deploy the product or enable live traffic automatically.

## AI policy

Cloud providers remain limited to YandexGPT and GigaChat. Local/self-hosted LLMs remain separately governed by the free-commercial-use and provenance requirements.

OpenAI is not an approved platform provider. No cloud/local fallback is introduced.

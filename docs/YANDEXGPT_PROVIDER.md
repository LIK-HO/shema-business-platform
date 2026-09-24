# YandexGPT Provider Adapter

## Evidence snapshot

This concrete provider boundary is based on the current official Yandex Cloud documentation checked on 2026-09-24.

- Yandex Cloud documents AI Studio text-generation APIs and the AI endpoint. Official service API index: https://yandex.cloud/en/docs/overview/api
- Current Yandex documentation shows the OpenAI-compatible AI Studio endpoint `https://ai.api.cloud.yandex.net/v1`, a model URI in `gpt://<folder_ID>/<model_ID>/latest` form, and use of `chat.completions.create`. See the current IDE integration guide: https://yandex.cloud/en/docs/tutorials/ml-ai/ai-model-ide-integration
- Current Yandex IAM documentation supports API-key authentication with `Authorization: Api-Key <API_key>` and the `yc.ai.languageModels.execute` scope for text-generation requests: https://yandex.cloud/en/docs/iam/concepts/authorization/api-key

## Implementation boundary

`YandexGPTProvider` is a concrete adapter under `src/shema_platform/adapters/ai/`. It does not modify `src/shema_platform/application/ai.py`, does not persist provider-owned state, and cannot become canonical business truth.

The adapter uses the provider-neutral P25 contract:

`descriptor → explicit activation → readiness → invoke → validated response`

## Security and resource controls

- API credentials are runtime-only and excluded from configuration `repr`.
- HTTPS is mandatory.
- Request execution is bounded by the provider timeout, operation deadline and AI budget.
- Prompt size, response body size and output-token count are bounded before/after external I/O.
- HTTP authentication, authorization and rate-limit failures are typed and fail closed.
- Provider-specific automatic retry is not implemented.
- Raw provider payloads are not part of the returned adapter response.
- Cost is not guessed: a concrete cost estimator is required and token usage must be present and internally consistent.

## Prompt materialization

The frozen `AITask` contract stores task type and prompt version but not raw prompt text. The adapter therefore requires an injected `prompt_renderer` and deliberately refuses empty prompt materialization. This keeps prompt semantics outside the provider adapter rather than inventing a hidden provider-specific prompt format.

## Activation

Concrete activation remains explicit. An environment-created configuration without a valid runtime API key is rejected. The provider is only ready after local configuration validation; an invocation failure moves the operational readiness state to `UNHEALTHY` and records only a typed error code.

## Scope stop

P26 currently covers the YandexGPT concrete adapter and its bounded test proof. It does not activate production traffic, add GigaChat, install a local model runtime, add cloud/local fallback, or change the frozen kernel.

Further integration of the adapter into a running application requires a separate bounded composition/activation proof.
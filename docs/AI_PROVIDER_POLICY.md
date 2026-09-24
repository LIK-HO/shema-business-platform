# AI Provider Policy

## Binding policy

Cloud AI providers are allowlisted to exactly two provider families:

- YandexGPT via Yandex Cloud AI Studio.
- GigaChat via GigaChat API.

All other cloud AI providers are denied by default. Adding another cloud provider requires an explicit architecture decision and a manifest update.

Local/self-hosted LLMs are supported when the model's license permits free use for the intended commercial scenario. The system must retain model identity/version, source, license evidence, license URL, verification date, artifact digest, runtime, resource limits and security status.

Free use means no mandatory license or API fee for the model itself. Compute, storage and infrastructure remain operating costs.

Both cloud and local models remain adapters behind the existing provider-neutral AI Gateway. They cannot own canonical business truth or bypass authorization, policy, evidence, budget, audit or persistence controls.

No implicit cloud-to-local or local-to-cloud fallback is allowed.

## Current external evidence

Yandex Cloud currently exposes AI Studio text-generation APIs and lists YandexGPT among its foundation-model capabilities. GigaChat currently exposes a public REST API and model catalog. These sources are used only to validate the existence of the approved cloud integration surfaces; provider implementation is a separate bounded task.

- https://yandex.cloud/en/docs/overview/api
- https://yandex.cloud/en/docs/console/operations/search
- https://developers.sber.ru/docs/ru/gigachat/api/reference/rest/gigachat-api
- https://developers.sber.ru/docs/ru/gigachat/models/gigachat-3-ultra

Evidence snapshot: 2026-09-24.

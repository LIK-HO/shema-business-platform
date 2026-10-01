# P33 — GigaChat Provider Contract + Bounded Adapter

P33 introduces the second approved cloud AI provider behind the frozen provider-neutral AI Gateway contract.

## Current official API contract

Current Sber documentation identifies `https://api.giga.chat` as the target GigaChat API base URL. OAuth access tokens are obtained with `POST /api/v2/oauth`, require an explicit scope and `RqUID`, and are valid for 30 minutes. citeturn505156search6turn675347view0

Text generation uses `POST /v1/chat/completions`. The current REST contract documents HTTP success/error classes and response model/token usage. citeturn675347view1turn407546search3

## Adapter boundary

`GigaChatProvider`:

- keeps the authorization key and OAuth access token runtime-only;
- serializes token refresh in-process;
- refreshes against the documented 30-minute token lifetime with a 30-second safety window;
- uses one bounded execution deadline across token acquisition and generation;
- performs no automatic retry;
- validates response text, requested-model identity and token accounting;
- delegates cost calculation to the existing injected estimator;
- never persists provider state;
- remains outside canonical business truth.

## Production commercial boundary

The current Sber documentation states that Freemium GigaChat API use is for personal non-commercial purposes, while commercial use requires a paid package. Therefore the production activation gate accepts only `GIGACHAT_API_B2B` and `GIGACHAT_API_CORP`, rejecting `GIGACHAT_API_PERS`. citeturn505156search2turn505156search5

## TLS

Sber's current quickstart instructs API users to install the Russian CA certificates required for GigaChat connectivity. The adapter requires HTTPS and does not disable TLS verification. citeturn505156search8

## Activation

`GigaChatProductionGate` is:

- disabled by default;
- activated only with an explicit operator;
- configured from an immutable snapshot;
- supplied with the runtime-only authorization key;
- bounded by cost and duration ceilings;
- explicitly rollbackable;
- not connected to application or HTTP routing in P33.

## Scope stop

P33 does not add OpenAI, another cloud provider, a local runtime, fallback routing, database schema changes, frozen-kernel changes, application wiring or live production traffic.

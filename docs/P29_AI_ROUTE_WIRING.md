# P29 Production YandexGPT Route Wiring

P29 adds the canonical HTTP experience boundary for one bounded AI execution.

## Boundary

POST /v1/ai/run is routed through the existing APIApplication protocol. The HTTP layer does not construct an AIGateway, select a provider, resolve trust levels, or persist AIRun state.

The request may carry:
- task type and prompt version;
- resource reference;
- input and evidence references;
- an explicit evidence-required flag;
- token, cost and duration ceilings.

The request may not carry:
- provider or model selection;
- actor/resource/evidence trust levels;
- production activation state;
- credentials.

## Production relation

The route is compatible with the P28 YandexGPT activation gate, but route exposure does not activate production traffic. A concrete application composition must inject an application implementation that uses the frozen AIGateway and the P27 composition/P28 gate.

When application composition is absent, the existing API boundary returns the existing application_unavailable / HTTP 503 response.

## Scope stop

P29 does not:
- modify application.ai;
- modify the frozen kernel;
- add GigaChat;
- add a local/self-hosted runtime;
- add provider fallback;
- add database schema or migration changes;
- let the HTTP client choose a provider;
- persist provider payloads at the HTTP edge.

## Verification target

The route must pass the existing API contract/runtime tests and the full seven-job CI gate before P29 can close.

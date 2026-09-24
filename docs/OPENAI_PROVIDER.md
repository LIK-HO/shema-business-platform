# OpenAI Provider Boundary

## Purpose

P24 adds one concrete AI provider behind the frozen \`AIProvider\` interface. The provider remains an adapter: it cannot become canonical business truth, bypass authorization/policy/evidence checks, or move external I/O into the Unit of Work.

## Current provider contract

The adapter uses the OpenAI Responses API at \`https://api.openai.com/v1/responses\`. The default model is \`gpt-6-luna\`; model and operational limits remain versioned configuration rather than hard-coded business policy.

Requests are stateless at the provider boundary: \`store=false\`, no tools are enabled, and no conversation/background execution mode is introduced by this adapter.

The readiness check uses \`GET /v1/models/{model}\`. It authenticates the runtime secret and verifies model visibility without performing inference.

The raw Responses payload is parsed explicitly. The adapter requires a completed response with a response id, model, consistent usage metrics and at least one \`message\` / \`output_text\` item; unrelated output item types are ignored.

## Activation boundary

Activation is explicit and versioned through \`ConfigurationSnapshot\`:

- \`ai.openai.enabled=true\` is required;
- \`OPENAI_API_KEY\` is read only from runtime secret state and is never copied into the snapshot;
- an input/prompt resolver is required so provider code does not invent access to canonical business data;
- an evidence resolver is required so provider evidence references remain explicit;
- production auto-activation is disabled.

The adapter accepts only the exact HTTPS origin \`api.openai.com\`. Any non-HTTPS base, alternate host, explicit port, query/fragment or redirect fails closed.

## Resource and cost controls

The adapter enforces before external I/O:

- input character bound;
- serialized request-body bound;
- output-token bound;
- response-byte bound;
- operation timeout bound;
- process-local request-rate bound;
- worst-case per-call cost guard.

The preflight cost calculation deliberately uses a conservative UTF-8 byte estimate for input plus the configured maximum output-token budget. It is an operational rejection guard, not a billing ledger.

After a successful response, actual usage is taken from provider-reported \`input_tokens\` and \`output_tokens\` and reconciled against \`total_tokens\`. Actual cost is calculated from the versioned pricing snapshot and is rejected when it exceeds the configured per-call cap.

The adapter does not implement automatic retries. Paid inference is not treated as idempotent, so a timeout or lost response must not silently multiply provider charges. A higher-level durable workflow may make an explicit retry decision later; P24 does not add that workflow.

## Output and evidence integrity

The adapter never reads canonical business state directly. It receives an input reference tuple and delegates prompt construction and evidence-reference resolution to injected boundaries.

The resulting \`AIRun\` retains:

- the provider response id;
- configured model and provider-reported model version;
- the task and prompt version;
- original input references;
- resolved evidence references;
- bounded text output;
- provider-reported token usage;
- calculated operational cost;
- measured duration.

The existing \`AIGateway\` remains authoritative for authorization, policy, caller-supplied evidence membership and durable audit/persistence.

## Persistence and recovery

The network call is made outside the existing Unit of Work. The \`AIGateway\` persists the resulting \`AIRun\` and audit record using canonical PostgreSQL authority.

P24 does not add a provider response store, AI-specific retry scheduler, billing ledger, or business-state writer.

## Security

- API keys exist only in runtime secret configuration;
- credentials are placed in the \`Authorization\` header, never the request URL;
- request/response bodies are not emitted to telemetry;
- HTTP redirects are rejected;
- provider-side response storage is disabled with \`store=false\`;
- no provider tools are enabled by this adapter;
- non-success and malformed responses fail closed without returning provider response bodies.

## External provider evidence

The 2026-09-24 contract snapshot is based on the current OpenAI public documentation for the Responses API, Models API, model catalog and production best-practices/rate-limit guidance.

The default model and default pricing values are configuration defaults tied to this evidence snapshot and are not canonical business or billing truth. Production configuration may select another currently supported model and pricing snapshot while remaining inside the same operational bounds.

## Release boundary

P24 changes only:

- \`src/shema_platform/adapters/ai/*\`
- \`architecture/openai_provider_contract.json\`
- \`docs/OPENAI_PROVIDER.md\`
- focused provider tests
- the productization state ledger after verification

No v1.4 kernel contract, application gateway semantics, PostgreSQL schema, migration, canonical business state or deployment rule is changed.

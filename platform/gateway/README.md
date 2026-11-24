# Model Gateway

**Status: not started.** Planned for Phase 1.

Model routing, per-service tokens, mTLS between services and gateway, usage logging, prompt and response guardrails, nightly benchmark job (plan Phase 1).

| Decision | Value | Source |
|---|---|---|
| Hosting | Hosted model APIs only; no local LLM, no fine-tuning | OD-5, [ADR-0005](../../docs/adr/0005-model-hosting.md) |
| Provider | OpenAI (`OPENAI_API_KEY` in `.env`) | OD-37 |
| Vision | Multimodal model over the API, also for block 1 | OD-38, [ADR-0007](../../docs/adr/0007-vision-via-multimodal-api.md) |
| Models | Not decided | OD-43 |

Planned stack: LiteLLM proxy (routing, keys, budgets, fallbacks, usage logs), step-ca, Keycloak, NeMo Guardrails, Presidio, Langfuse, DeepEval (plan Phase 1, §4.1). vLLM is dropped by OD-5.

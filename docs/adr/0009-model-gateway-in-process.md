# ADR-0009: Model Gateway as an in-process LiteLLM library for the POC

| | |
|---|---|
| Status | Proposed |
| Date | 2026-11-25 |
| Phase | Phase 1, Model Gateway (plan §6 Phase 1) |

## Context

Plan Phase 1 builds the Model Gateway: "Model routing, per-service tokens, mTLS between services and gateway, usage logging, prompt and response guardrails, nightly benchmark job", on "LiteLLM proxy, vLLM, step-ca, Keycloak, NeMo Guardrails, Presidio, Langfuse, DeepEval". Exit criterion: "Every gateway call is authenticated with mTLS and logged with tokens and cost" (plan Phase 1).

Plan §4.1 rows: LiteLLM proxy (MIT) "Per-team keys, budgets, fallbacks, usage logs"; step-ca for mTLS; NeMo Guardrails and Presidio for "Prompt-injection screening, PII redaction on prompts and logs"; Langfuse for "Self-hosted traces, prompt versions, cost"; DeepEval and lm-evaluation-harness for "benchmark scores". Plan §10 risk 7: "Guardrails at the gateway, treat drawing text as data, no tool calls driven by extracted text".

Owner decisions that change the setting:

- OD-5, ADR-0005: hosted OpenAI API only; vLLM is dropped.
- OD-21 (2026-11-25): no containers for the POC; ADR-0008 local adapters stay.
- OD-39 (2026-11-25): drawings may go to the API for the POC. Organisation policy still forbids client-identifying information and personal data in prompts to external systems.
- OD-43, OD-42: gpt-5.5 for every role, text-embedding-3-large for embeddings.

The deck routes every AI request through the gateway ("One door", deck slide 64).

## Options considered

| Option | Source | Notes |
|---|---|---|
| A. LiteLLM proxy server, with Presidio, NeMo Guardrails, Langfuse, step-ca, Keycloak | plan Phase 1, §4.1 | Needs Postgres and Langfuse services and a certificate authority; containers are out for the POC (OD-21). Presidio needs a spaCy language model download |
| B. LiteLLM SDK inside one `edp_gateway` package, with deterministic redaction, data-wrapping guard and a SQLite usage log | this ADR | Same routing library and cost map as A, no extra services. Blocks call one class; nothing else holds the key |
| C. OpenAI SDK directly | not in plan | Fewer dependencies, but no cost map: per-token prices would have to be typed in, which the repo rules forbid without a source |

## Decision

Proposed: **Option B** for the POC.

- `platform/gateway` (`edp_gateway`) is the only code that holds the API key and calls a model. Blocks use `Gateway.complete(...)` and `Gateway.embed(...)`.
- Routing: role (`text`, `vision`, `code`, `judge`) to model from `.env` (OD-43); embeddings from `EDP_EMBEDDING_MODEL` (OD-42).
- Cost: LiteLLM's bundled model cost map for the pinned LiteLLM version (never fetched from the network). gpt-5.5 is listed at 5e-06 USD per input token and 3e-05 per output token; text-embedding-3-large at 1.3e-07 per input token (LiteLLM 1.111.0). A model missing from the map is logged with tokens and flagged `COST_UNKNOWN`.
- Usage log: one SQLite row per call (service, run, role, model, prompt version, data class, status, tokens, cost, latency, redaction counts, flags, prompt hash), with no prompt or response text (plan §4.1: "PII redaction on prompts and logs").
- Budget: optional `EDP_LLM_BUDGET_USD`; calls are refused once the logged spend reaches it (plan §4.1 "budgets"; value open, OD-50).
- Redaction before every call: `EDP_REDACT_TERMS`, e-mail addresses, phone numbers, identifying title-block labels (OD-51 replaces Presidio for now).
- Injection handling: untrusted text only inside `<data>` elements with a fixed rule in the system message; screening flags known phrasings for review; no tool calls (plan §10 risk 7; OD-51 replaces NeMo Guardrails for now).
- Images: allowed for synthetic and internal data; refused for client data until title-block masking exists (OD-39, OD-51).

## Consequences

- Plan Phase 1 exit criterion "logged with tokens and cost" is met locally. "Authenticated with mTLS" does not apply while the gateway runs in-process: there is no network hop to authenticate. It returns with Option A.
- Per-service tokens (Keycloak) become the `service` field on each call; there is no separate credential per block.
- Langfuse traces are replaced by the usage log; prompt versions are recorded per call.
- The nightly benchmark job (DeepEval) is not built yet (phase-1 log).
- LiteLLM brings 40-odd dependencies; four needed reviewed licence exceptions (python-dateutil, regex, tiktoken, tokenizers; [license-policy.md](../policies/license-policy.md)).
- Moving to Option A later changes only `backend.py`: the LiteLLM proxy speaks the same API.

## Open items

- OD-50: budget, timeout and retry values (not in plan or deck).
- OD-51: Presidio and NeMo Guardrails replacements; title-block label list; image masking for client drawings.
- OD-31: approve `CNRI-Python` (regex).
- Who accepts this ADR: not specified in plan or deck (see [README.md](README.md)).

## Sources

- Plan §4.1 (LiteLLM, step-ca, NeMo Guardrails, Presidio, Langfuse, DeepEval rows), §6 Phase 1, §10 risk 7, Appendix A (`gateway/`).
- Deck slide 64.
- OD-5, OD-21, OD-39, OD-42, OD-43, OD-50, OD-51; ADR-0005, ADR-0007, ADR-0008.

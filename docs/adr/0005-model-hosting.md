# ADR-0005: Model hosting

| | |
|---|---|
| Status | **Accepted, amended** by the project owner's answer to OD-5 (2026-11-24). The amendment below replaces Option A |
| Date | 2026-11-24 (proposed), 2026-11-24 (accepted) |
| Phase | Phase 0, task 7 (plan §6 Phase 0); built in Phase 1 |

## Context

The Model Gateway is a platform service used by blocks 2, 4 and 8 and by the Optimiser (plan §2.1). The plan uses models for parsing, generation and reports:

- Block 1: Qwen2.5-VL / Qwen3-VL or Florence-2 for title blocks, notes and GD&T. "Qwen licenses differ by model size" (plan §4.2).
- Block 4: Qwen2.5-Coder / Qwen3-Coder via vLLM (plan §4.2); "Qwen-Coder family via vLLM" (plan Phase 4).
- Block 8: narrative drafted by an LLM through the Model Gateway; every number inserted from the Run Store by code (plan Phase 6).

What the plan chooses (plan §4.1):

| Need | Primary choice | Licence | Alternative | Notes (as given in the plan) |
|---|---|---|---|---|
| Model serving | vLLM | Apache 2.0 | Ollama (MIT) for dev | "Self-hosted VLM and code models" |
| Model routing, usage log | LiteLLM proxy (OSS edition) | MIT | Envoy AI Gateway (Apache 2.0) | "Per-team keys, budgets, fallbacks, usage logs" |

Phase 1 builds the Model Gateway: "Model routing, per-service tokens, mTLS between services and gateway, usage logging, prompt and response guardrails, nightly benchmark job", on LiteLLM proxy, vLLM, step-ca, Keycloak, NeMo Guardrails, Presidio, Langfuse and DeepEval (plan Phase 1). Exit criterion: "Every gateway call is authenticated with mTLS and logged with tokens and cost" (plan Phase 1).

Other constraints in the plan:

- Model weights: "Qwen, Llama and other model weights: Licenses vary by family and size. Check per model before deployment" (plan §9).
- Phase 0 task 8: "Hardware sizing: GPU needs for the VLM and code model" (plan Phase 0).
- Risk 9, GPU capacity: "Size in Phase 0, quantised models, gateway fallbacks" (plan §10).
- Risk 7, prompt injection: "Guardrails at the gateway" (plan §10).
- Principle 7: client data stays in client scope (plan §2.3).
- Open question 5: "GPU budget for self-hosted models, and whether any hosted model APIs are allowed for non-client data" (plan §11).

What the deck says:

- Gateway request path step 7, "Model adapter: in-house, Bedrock, custom". Model hosts include "GPU serving on a shared CUDA pool, reachable only through the gateway", "on-premise or offline models", "hosted models with guardrails" and "fine-tuned CAD models, one grant each" (deck slide 45).
- Gateway stack: "Python, FastAPI; open model server on GPU servers; AWS Bedrock; mutual TLS; JWT", status "Confirmed: in-house and AWS Bedrock. Server runtime proposed" (deck slide 62).
- "One door: every AI request goes through the Model Gateway"; "Model servers accept the gateway only" (deck slide 64).
- Risk "Output quality of in-house models", mitigation "Benchmarks and routing; Bedrock as an alternative per project" (deck slide 88).
- "Reuse the existing serving engine and routing" (deck slide 89).
- Prerequisite "GPU pool for 7B to 14B models; CPU nodes for FEA and surrogate inference", needed by week 0 (deck slide 90).
- Hosting per target industry ranges from "In-house" and "In-house, isolated" to "In-house or hybrid" and "Either, per customer" (deck slide 93).

The deck does not name the server runtime. The Bedrock difference is logged as D6 ([plan-vs-deck.md](../reference/plan-vs-deck.md)).

## Options considered

| Option | Source | Notes |
|---|---|---|
| A. Self-hosted vLLM for serving, LiteLLM proxy (OSS edition) for routing and usage logs | plan §4.1, Phase 1 | The plan's primary choice. Apache 2.0 and MIT (plan §4.1) |
| B. Ollama for dev serving; Envoy AI Gateway for routing | plan §4.1 (alternatives) | Ollama is MIT and listed "for dev". Envoy AI Gateway is Apache 2.0 (plan §4.1) |
| C. In-house models plus AWS Bedrock | deck slides 45, 62, 88 | Deck position, D6. The deck marks it "Confirmed" (deck slide 62). Plan §11 question 5 leaves hosted model APIs open. Bedrock terms are not stated in plan or deck |

## Decision (accepted 2026-11-24)

Project owner's answer to OD-5: **"api calls only no fine tuning or local llm"**.

- All LLM and VLM work uses **hosted model APIs**. No self-hosted serving: vLLM and Ollama are dropped.
- **No fine-tuning.** This drops the optional fine-tune in plan Phase 4 Generation task 2 ("optionally fine-tuned using CAD-Coder or Text-to-CadQuery style data") and the deck's SFT loop (deck slide 28, F-23).
- The **LiteLLM proxy (OSS edition)** stays as the routing and usage-log layer (plan §4.1: "Per-team keys, budgets, fallbacks, usage logs"). Calls still go through the gateway with guardrails and usage logging (plan Phase 1).
- **Provider: OpenAI** (OD-37, decided 2026-11-24). The key is `OPENAI_API_KEY` in `.env`. Model names are open (OD-43). The deck had named AWS Bedrock (deck slides 45, 62, 88); the plan named no provider.
- Vision, OCR and symbol reading also use a multimodal model over the API ([ADR-0007](0007-vision-via-multimodal-api.md), OD-38).

The original proposal is kept below for the record.

### Original proposal (superseded)

Proposed: **Option A**. Models are self-hosted and served with vLLM (plan §4.1, Phase 1). Gateway calls go through the LiteLLM proxy (OSS edition) for routing and usage logs (plan §4.1, Phase 1). The plan connects the gateway to blocks 2, 4, 8 and the Optimiser (plan §2.1). Whether block 1 calls go through it is an open item (see Open items). The alternatives the plan lists are Ollama for development serving and Envoy AI Gateway for routing (plan §4.1).

Hosted model APIs, including AWS Bedrock, are not part of this proposal. The plan asks whether they are allowed for non-client data (plan §11 question 5, OD-5). The deck's position is in-house plus AWS Bedrock (D6, deck slides 62, 88). This is open as OD-11 and this ADR does not settle it.

## Consequences

Consequences of the accepted decision:

- **GPU sizing for LLMs is no longer needed.** OD-20 and OD-23 shrink to CPU sizing for meshing and solvers. GPU needs for non-LLM vision models are open (OD-38).
- Qwen-VL, Qwen-Coder and other weight licences (plan §4.2, §9) no longer apply. **OpenAI's terms and data-usage policy** replace them and must be reviewed before use with any data (OD-37, OD-39).
- **Client data and external APIs.** Principle 7 says client data stays in client scope (plan §2.3). Sending a client drawing to an external API needs that client's permission under its SOW. The gateway guardrails (Presidio for PII redaction, NeMo Guardrails, plan §4.1) apply to every call. Until a client permits it, only internal or openly licensed data goes to external APIs (OD-39).
- Plan §10 risk 9 (GPU capacity) is replaced by API rate limits, cost and availability. Gateway fallbacks (plan §4.1, LiteLLM "fallbacks") are the mitigation.
- The "nightly benchmark job" (plan Phase 1) still applies: it benchmarks hosted models per task (plan §7, Gateway row).

Consequences recorded with the original proposal:

- Phase 1 builds the Model Gateway on LiteLLM proxy, vLLM, step-ca, Keycloak, NeMo Guardrails, Presidio, Langfuse and DeepEval (plan Phase 1). Its config, guardrails and benchmarks go in `platform/gateway/` (plan Appendix A).
- In the plan's layer diagram the Model Gateway serves blocks 2, 4, 8 and the Optimiser (plan §2.1). The deck says every AI request goes through the gateway (deck slide 64). The plan does not say whether block 1's VLM calls (plan §4.2, Phase 2) go through the gateway; see Open items.
- Every gateway call is authenticated with mTLS and logged with tokens and cost (plan Phase 1 exit criteria).
- GPU capacity has to be sized in Phase 0 (plan Phase 0 task 8, §10 risk 9). The plan gives no GPU numbers. The deck gives "GPU pool for 7B to 14B models" (deck slide 90).
- Each model's weights licence is checked before deployment; Qwen licences differ by model size (plan §4.2, §9).
- Licences of the serving and routing tools: vLLM Apache 2.0, LiteLLM proxy (OSS edition) MIT, Ollama MIT, Envoy AI Gateway Apache 2.0 (plan §4.1). All are to be confirmed in the Phase 0 licence scan (plan §4 preamble, Phase 0 task 6).
- If hosted APIs are allowed later (OD-5, OD-11), principle 7 still applies: client data stays in client scope (plan §2.3). The plan's question 5 is limited to "non-client data" (plan §11).

## Open items

- OD-11 and OD-5: **Decided 2026-11-24**: hosted APIs only, no fine-tuning, no local LLM.
- OD-37: provider. **Decided 2026-11-24: OpenAI.**
- OD-43: which OpenAI models for text, vision, code and judge. Open.
- OD-38: whether "no local LLM" also excludes local non-LLM models (symbol detector, OCR, embeddings). Open.
- OD-39: rules for sending client data to external APIs. Open.
- OD-20 and OD-23: GPU type, count and hosting; CPU solver nodes. Open.
- OD-24: which models to host, with their licences. Open.
- OD-25: certificate authority and revocation process. The plan picks step-ca (plan §4.1). Open.
- OD-2: hosted by Calsoft, deployed into client environments, or both. This affects where models run. Open.
- Whether block 1 (Drawing Parser) calls its VLM through the Model Gateway: not stated in the plan (plan §2.1 does not connect the gateway to block 1). The deck routes every AI request through the gateway (deck slide 64). No OD id yet.
- Who accepts this ADR: not specified in plan or deck (see [README.md](README.md)).

## Sources

- Plan §2.1, §2.3 (principle 7), §4 (preamble), §4.1, §4.2 (blocks 1 and 4), §6 Phase 0 (tasks 6, 7 and 8), Phase 1, Phase 2, Phase 4, Phase 6, §9, §10 (risks 7 and 9), §11 (question 5), Appendix A.
- Deck slides 45, 62, 64, 88, 89, 90, 93.
- [plan-vs-deck.md](../reference/plan-vs-deck.md): D6.
- [open-decisions.md](../open-decisions.md): OD-2, OD-5, OD-11, OD-20, OD-23, OD-24, OD-25.

# Model Gateway

**Status: built for the POC (2026-11-25)**, as an in-process library ([ADR-0009](../../docs/adr/0009-model-gateway-in-process.md)). Plan Phase 1: "Model routing, per-service tokens, mTLS between services and gateway, usage logging, prompt and response guardrails, nightly benchmark job".

The gateway is the only code that holds the OpenAI key or calls a model. Blocks call it like this:

```python
from edp_gateway import CompletionRequest, Gateway, GatewayConfig

gw = Gateway(GatewayConfig.load())  # reads .env; the key never leaves the backend
res = gw.complete(
    CompletionRequest(
        service="b2_interpretation",
        role="text",
        prompt_version="notes-1",
        data_class="synthetic",
        instructions="Extract the material and finish from the notes.",  # trusted, versioned
        inputs=[note_text],  # untrusted: sent as <data>
        run_id=run_id,
    ),
    output_model=NotesModel,  # pydantic model: JSON schema out, validated reply in
)
res.parsed, res.usage.cost_usd, res.flags
gw.embed("b3_knowledge_graph", texts, data_class="synthetic").vectors
```

## What every call goes through

| Step | What | Source |
|---|---|---|
| Routing | Role `text`, `vision`, `code`, `judge` to `EDP_LLM_MODEL_*`; embeddings to `EDP_EMBEDDING_MODEL` | OD-43, OD-42 |
| Images | Client-data images refused until title-block masking exists | OD-39, OD-51 |
| Redaction | `EDP_REDACT_TERMS`, e-mails, phone numbers (8+ digits), identifying title-block labels; plain numbers and tolerances untouched | OD-39, organisation policy, OD-51 |
| Injection guard | Untrusted text only inside `<data>`; screened for known phrasings (flag, not block); no tool calls | plan §10 risk 7, OD-51 |
| Budget | Refuse once logged spend reaches `EDP_LLM_BUDGET_USD` (blank: no limit) | plan §4.1 "budgets", OD-50 |
| Call | LiteLLM SDK; JSON-schema output validated against the caller's model | plan §4.1 |
| Usage log | SQLite `<EDP_DATA_DIR>/gateway/usage.sqlite`: tokens, cost, latency, flags, prompt hash; no prompt text | plan Phase 1 exit criterion |

Cost comes from LiteLLM's bundled model cost map (pinned by `uv.lock`, never fetched): gpt-5.5 5e-06 USD per input token, 3e-05 per output token; text-embedding-3-large 1.3e-07 per input token (LiteLLM 1.111.0).

Flags on results use the contract's `Flag`: `PROMPT_INJECTION_SUSPECTED` (review), `REDACTED` (info), `COST_UNKNOWN` (info).

## Commands

```bash
uv run python -m edp_gateway check   # one tiny synthetic call per role + one embedding; never prints the key
uv run python -m edp_gateway usage   # spend and totals from the usage log
```

## Settings (`.env`)

| Variable | Meaning |
|---|---|
| `OPENAI_API_KEY` | Never committed, printed or logged |
| `EDP_LLM_MODEL_TEXT`, `_VISION`, `_CODE`, `_JUDGE` | gpt-5.5 (OD-43) |
| `EDP_EMBEDDING_MODEL` | text-embedding-3-large (OD-42) |
| `EDP_LLM_BUDGET_USD` | Blank: no limit (OD-50) |
| `EDP_LLM_TIMEOUT_S`, `EDP_LLM_MAX_RETRIES` | Blank: LiteLLM defaults (OD-50) |
| `EDP_REDACT_TERMS` | Comma-separated client and company names to remove; kept only in `.env` |

## Not built yet

- Nightly benchmark job (plan Phase 1; DeepEval).
- mTLS and per-service credentials: not applicable in-process (ADR-0009).
- Presidio and NeMo Guardrails (OD-51); title-block masking for client images (OD-51).

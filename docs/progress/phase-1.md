# Phase 1 log: Platform services and orchestrator skeleton

| | |
|---|---|
| Plan reference | plan §6 Phase 1 (4 weeks, R1) |
| Status | In progress. Walking skeleton, console shell and Model Gateway (in-process, ADR-0009) built; MCP wrappers, chat panel and the nightly benchmark not started |
| Last updated | 2026-11-25 |

## 1. Approach

The owner asked to start implementation without a container runtime (OD-21). [ADR-0008](../adr/0008-local-first-adapters.md) puts every external service behind an interface and ships a local adapter for each:

| Plan service | Local adapter |
|---|---|
| NATS JetStream | In-memory event bus |
| SeaweedFS + lakeFS | Filesystem zones with content-hash commits |
| PostgreSQL (catalogue, checkpoints) | SQLite |

## 2. What was built

| Package | Folder | What it does |
|---|---|---|
| edp-kit | `platform/kit/` | Event bus interface and in-memory bus (known subjects only). `run_block()` publishes the `run.block.*` events. `create_block_app()` serves any block on `/run`, `/health`, `/contract` (plan §3) |
| edp-fabric | `platform/fabric/` | Upload with type detection from content (deck slide 42); raw, cleaned and final zones; immutable commits; `fabric.*` events with the Appendix B payloads; HTTP API |
| edp-catalogue | `platform/catalogue/` | Artifact registry and element-level lineage in SQLite; trace back from a file; `catalogue.lineage.recorded`; HTTP API |
| edp-orchestrator | `orchestrator/` | LangGraph planner and block nodes in R1 order; stub blocks 1 to 8; SQLite checkpointer; human-review pause and approve/reject; CLI `python -m edp_orchestrator` |

New dependencies: fastapi, httpx, python-multipart, langgraph, langgraph-checkpoint-sqlite, langchain-core. All pass the licence gate except `sqlite-vec` (a dependency of the SQLite checkpointer). Its metadata is the single string "MIT License, Apache License, Version 2.0", which the gate cannot split, so it has a scoped exception quoting that text. MIT and Apache-2.0 are both allowed by plan §9.

## 3. Phase 1 exit criteria (plan)

| Criterion | Status |
|---|---|
| A file uploaded in the console produces a versioned dataset, a run with eight stub block results, lineage visible in Marquez, and an end-to-end trace in Langfuse | **Partly met.** Upload from the console works (2026-11-25). Upload → versioned dataset → run with eight stub results → element-level lineage from the report back to the file commit works and is tested (`test_upload_to_eight_stub_results_with_lineage`). Not yet: upload from the console (console not built), Marquez and Langfuse (need containers, OD-21) |
| Every gateway call is authenticated with mTLS and logged with tokens and cost | **Logging met locally** (2026-11-25): every call, refused and failed ones included, is a usage-log row with tokens and cost. mTLS does not apply in-process; it returns with the proxy (ADR-0009, OD-21) |
| Restarting any block mid-run resumes from the checkpoint | **Met locally.** `test_restart_mid_run_resumes_from_checkpoint`: block 5 crashes, a new orchestrator instance on the same checkpoint store resumes, and blocks 1 to 4 are not re-run |

## 4. Problems found and fixed

- **New workspace packages did not import.** They were first installed while their folders held only `py.typed`, so no editable path file was written. Fixed with `uv sync --reinstall-package ...`.
- **Python's `platform` module was hidden during tests.** Pytest's importlib mode named test modules after their path (`platform.fabric.tests...`) and put a fake `platform` package in `sys.modules`, which broke ezdxf. Fixed by going back to pytest's default import mode. All test file names are already unique; that rule is now in CLAUDE.md.
- **mypy:** LangGraph expects `RunnableConfig`; `_config()` is typed accordingly, and `langchain-core` is declared explicitly.

## 5. Verification (2026-11-25)

```text
$ bash scripts/ci/run_ci.sh
Lint (ruff)            All checks passed!
Type check (mypy)      Success: no issues found in 35 source files
Tests (pytest)         183 passed
Requirements           requirements.txt and requirements-dev.txt match uv.lock
Licence gate           63 distributions checked: 61 pass, 0 warn, 2 exception, 0 fail. Gate PASSED.

$ uv run python -m edp_orchestrator --file eval/golden/data/synthetic/syn-iso-plate-000.dxf --data-dir var --run-id demo-1
run demo-1: completed; b1_parser ... b8_report all ok; 27 events;
report traces back to: <file hash>@<commit>
```

## 6. Next in Phase 1

1. **Model Gateway: built 2026-11-25** (§7). Still open: nightly benchmark job (DeepEval), Presidio and NeMo Guardrails (OD-51), image masking for client drawings (OD-51).
2. **Console shell: built 2026-11-25** ([console/README.md](../../console/README.md)). Pipeline map with live block status over SSE, drawing sheet with source tracing, inspector, review actions, run events; local console API `edp_orchestrator.server`. **Chat panel built 2026-11-25** (§8).
3. **MCP wrappers** per block (plan §2.2, §3).
4. When containers are available (OD-21): swap the adapters for NATS, SeaweedFS + lakeFS, PostgreSQL, Marquez, Langfuse, step-ca.

## 7. Model Gateway (2026-11-25)

Built `platform/gateway` (`edp_gateway`) as an in-process library on the LiteLLM SDK ([ADR-0009](../adr/0009-model-gateway-in-process.md), [README](../../platform/gateway/README.md)). Every call: role routing from `.env` (OD-43, OD-42), refusal of client images (OD-39, OD-51), redaction, `<data>` wrapping and injection screening of untrusted text (plan §10 risk 7), budget check (OD-50), LiteLLM call with JSON-schema output validated by pydantic, and a usage-log row with tokens and cost but no prompt text.

| Item | Detail |
|---|---|
| Files | `platform/gateway/src/edp_gateway/{config,redact,guard,usage,backend,gateway,__main__}.py`, `tests/test_gateway.py` (14 tests, fake backend, no network) |
| Cost source | LiteLLM 1.111.0 bundled cost map, never fetched: gpt-5.5 5e-06 / 3e-05 USD per input / output token; text-embedding-3-large 1.3e-07 |
| Licences | LiteLLM MIT (no `litellm/enterprise/` folder in the wheel). Reviewed exceptions: python-dateutil, regex (CNRI-Python, OD-31), tiktoken, tokenizers |
| Problem found | The first phone-number rule redacted tolerances such as `+0.1/-0.0`. Now a `+` number may not contain `.` or `/` and needs 8+ digits; a test keeps tolerances, dimensions and standards text intact |

Verification:

```text
uv run pytest platform/gateway/tests: 14 passed
uv run python -m edp_gateway check (live, synthetic text only):
  code/judge/text/vision gpt-5.5: ok, reply 'ready', 54+12 tokens, 0.00063 USD each (54 x 5e-06 + 12 x 3e-05)
  embed text-embedding-3-large: ok, 3072 dimensions, 5 tokens, 6.5e-07 USD
uv run python -m edp_gateway usage: 5 calls logged, 0.00252 USD; the usage database holds no prompt text
```

## 8. Console chat panel and cited answers (2026-11-25)

Plan Phase 1 console shell: "Chat panel ... React, assistant-ui"; Data Catalogue: "cited answer" endpoint.

| Item | Detail |
|---|---|
| Cited answers | `platform/catalogue/src/edp_catalogue/answer.py`: run artifacts become numbered facts (`UNITS`, `TB.*`, `D1..`, `T1..` up to 80 texts, `S1`, `S1.H1`, design-graph node ids, `SP1..`, `KG.*`, `FL1..`), each with its source handles. Prompt `cited-answer-1`: answer only from the facts, cite their ids, say when the facts do not answer. Unknown ids are dropped and flagged; an uncited "supported" answer is flagged |
| Gateway | New `user` field: the engineer's question goes as the request, the facts and earlier turns as `<data>`; all redacted |
| Console API | `GET /api/chat` (available, model or reason), `POST /api/runs/{id}/chat`, `GET /api/usage`. Samples are `synthetic` data; uploads are `client` data (OD-39) |
| UI | "Ask about it" tab beside "Read from the drawing": assistant-ui 0.15.38 (MIT) thread and composer, three suggested questions, answers with clickable citations that highlight the drawing, a note when the facts do not support an answer, tokens and cost per answer, total spend |
| npm | assistant-ui brings 91 packages (100 to 191); the npm licence gate passes (ISC, 0BSD and OFL-1.1 still pending OD-31). The bundle is now over 500 kB; code splitting is a later improvement |

Verification:

```text
uv run pytest platform/catalogue/tests orchestrator/tests/test_console_api.py: catalogue 8 passed (4 new), console API 5 passed (2 new)
bash scripts/ci/run_ci.sh: exit 0; mypy 71 files; 252 passed; licence gates pass (Python 106 pass + 7 exceptions; npm 191)
Live, syn-iso-plate-000: "List the holes with their diameters." -> four holes, 5.5 mm, citing hole1..hole4.diameter
  (labels: four holes, diameter 5.5); 1182 + 67 tokens, 0.0079 USD
Live, same run: "What surface finish is required?" -> from_facts false, no citations: "The provided facts do not state any required surface finish."
Headless Edge (CDP script) at 1440x900 and 390x844: suggestion clicked, answer rendered, first citation highlights the hole on the sheet; phone page width 390 (no sideways scroll)
```

## 9. Console upgrade and end-to-end tests (2026-11-25)

Owner feedback: the console looked basic. Rebuilt the layout and the drawing view; several items are plan Phase 6 console work done early.

| Item | Detail |
|---|---|
| Layout | Pipeline as a strip across the top (React Flow, flag counts per block); runs list on the left; drawing or 3D view in the middle; Read and Ask tabs on the right; run events in a drawer |
| Drawing workspace | `Workspace.tsx`: pan, zoom (wheel, buttons, keys), fit; layer switches with counts; feature markers from the design graph that trace on click; pointer readout; readable minimum label size; scan image underneath scans |
| 3D viewer | `Viewer3D.tsx` with three.js 0.187 (MIT), loaded on demand; `edp_b1_parser.mesh` tessellates STEP and IGES with OCP (faces keep their entity ids) and serves STL as is; hole axes and rings; selected hole faces highlighted |
| API | `GET /api/runs`, `GET /api/runs/{id}/source` (scan images only), `GET /api/runs/{id}/mesh` (3D only, cached per run) |
| Tests | Playwright 1.65 (Apache-2.0, dev only) with the installed Edge: 6 end-to-end tests; Python test for the three endpoints |
| Bug found by the tests | Feature markers took clicks only on their outline; now the whole marker area does |
| Finding | The Knowledge Graph ingests misread scans and unnamed models (OD-54) |

Verification: `npm run test:e2e` 6 passed; headless Edge screenshots of a DXF run (feature selected), a STEP run (hole highlighted), a scan run (image under the read values) and a 390-pixel phone layout (no sideways scroll).

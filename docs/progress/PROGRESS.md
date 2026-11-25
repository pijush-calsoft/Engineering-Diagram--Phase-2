# Progress tracker

Read this first in every session. Update it at the end of every session (see [CLAUDE.md](../../CLAUDE.md)).

**Current phases: Phase 3 in progress (Interpretation and Knowledge Graph built; requirements parsing and embeddings pending OD-43/OD-42); Phase 2 mostly done (all inputs except scans); Phase 1 gateway pending the OpenAI key in `.env` (models chosen, OD-43); Phase 0 sign-off pending.**

## Phases (plan §5)

| Phase | Name | Release | Plan duration | Status | Log |
|---|---|---|---|---|---|
| 0 | Discovery, golden data and foundations | R1 | 4 weeks | **In progress**: golden DXF set done; sign-off pending | [phase-0.md](phase-0.md) |
| 1 | Platform services and orchestrator skeleton | R1 | 4 weeks | **In progress**: walking skeleton and console shell built (local adapters, ADR-0008); Model Gateway and MCP wrappers pending | [phase-1.md](phase-1.md) |
| 2 | Drawing Parser | R1 | 5 weeks | **Mostly done**: DXF, DWG, vector PDF, STEP, IGES, STL built and evaluated on synthetic sets; scans wait for OD-43; calibration needs real drawings | [phase-2.md](phase-2.md) |
| 3 | Interpretation and Knowledge Graph | R1 | 4 weeks | **In progress**: blocks 2 and 3 built; all three Phase 3 exit targets met on the synthetic family set; requirements parsing and embeddings pending | [phase-3.md](phase-3.md) |
| 4 | Generation and OpenCAD Adapters | R1 | 5 weeks | Not started | |
| 5 | Solver Connectors and Surrogate | R1 | 6 weeks | Not started | |
| 6 | Insight, audit trail and R1 hardening | R1 | 4 weeks | Not started | |
| 7 | Optimiser, redlines and write-back | R2 | 6 weeks | Not started | |
| 8 | Digital twin | R3 | 8 weeks | Not started | |

The plan's phases are the baseline (OD-8, decided: "take time to complete all"). The plan's dates assume a start of 7 Dec 2026.

## Phase 0 checklist (plan §6 Phase 0, key tasks)

| # | Task | Status | Output |
|---|---|---|---|
| 1 | Convert each block's In/Out line into acceptance criteria | **Draft done**, needs director sign-off. No In/Out lines exist in the deck in this repo (OD-14), so criteria come from the plan's exit criteria | [acceptance-criteria.md](../requirements/acceptance-criteria.md) |
| 2 | Golden dataset: 60 to 100 drawings plus 20 STEP/STL, hand-labelled | **DXF slice done.** No internal set exists (OD-7), so 80 synthetic DXF drawings were generated with exact labels (ISO and ASME, plate and bracket). PDF/scan slices and the 20 STEP/STL models are pending; public candidates found ([golden-data-sources.md](../reference/golden-data-sources.md)), need licence sign-off | [eval/](../../eval/README.md) |
| 3 | Define R1 part families | **Decided** (OD-1, OD-12, 2026-11-25): ISO and ASME; the plan's prismatic machined parts and sheet-metal brackets plus the deck's seat-structure pack (seat frame, recliner bracket). Golden data has plates and brackets; seat frame pending | |
| 4 | Plug-in contract v0.1 and artifact schemas | **Done** (v0.1.0). Deck additions not included pending OD-15 | [contracts/](../../contracts/README.md) |
| 5 | Monorepo, CI (lint, types, tests, licence scan, SBOM), container build, dev Kubernetes | **Done for the POC.** uv workspace, requirements files synced with `uv.lock`, provider-neutral CI script run locally before each commit (OD-18; run manually, no git hook, owner's choice). No containers or Kubernetes in the POC (OD-21). Syft and ScanCode not installed | [scripts/ci/](../../scripts/ci/README.md) |
| 6 | Licence policy and first ScanCode scan | **Policy and gate done**; ScanCode scan not run (tool not installed). Policy additions need sign-off (OD-31 to OD-36) | [license-policy.md](../policies/license-policy.md) |
| 7 | ADRs for orchestrator, event bus, graph store, object storage, model hosting | **Done.** ADR-0001 and 0005 Accepted, ADR-0006 (R2 write-back) Accepted; 0002 to 0004 Proposed; 0007 and 0008 reserved (OD-19) | [adr/](../adr/README.md) |
| 8 | Hardware sizing | **Mostly decided**: no GPU needed. All LLM and vision work goes through the OpenAI API (OD-5, OD-37, OD-38). Local CPU sizing for solvers is left to Phase 5 (OD-20) | |

### Phase 0 exit criteria (plan)

| Criterion | Status |
|---|---|
| Director signs off R1 part families and metrics | Not met: standards decided (OD-1); families awaiting confirmation (OD-12); acceptance criteria awaiting review |
| Golden dataset has at least 60 labelled drawings | **Met locally**: 80 labelled synthetic DXF drawings; `phase0_exit_check()` passed=True. Covers vector DXF only |
| CI blocks any AGPL dependency imported in-process | **Met locally.** `python -m edp_ci.license_gate` fails on GPL, AGPL, SSPL, BUSL and RSAL, and on unknown licences. Not yet wired into a CI provider (OD-18) |

## What the next session should do

0. Phase 3 still open: requirements parsing (OD-43), embeddings (OD-42), AGE/Postgres store (OD-21), interpretation of PDF and 3D inputs. Next candidates: Phase 4 Generation, Phase 5 OpenCAD Adapters.
0. Phase 2 still open: scans (OD-43), real-drawing golden data, calibration, LibreDWG version (OD-49) ([phase-2.md](phase-2.md)).
0. Phase 1 still open (console shell done): Model Gateway client (OpenAI through LiteLLM; needs `OPENAI_API_KEY` and OD-43 models), console shell (React, chat panel, pipeline map from `run.*` events), MCP wrappers.
1. Confirm OD-12 (part families) and the three recorded interpretations (OD-1, OD-6, OD-9).
2. Owner actions: none blocking the gateway; the OpenAI key in `.env` works (checked 2026-11-25: gpt-5.5 and text-embedding-3-large reachable). Decided 2026-11-25: OD-5, OD-10, OD-12, OD-18, OD-21, OD-39 (POC, with client identifiers removed), OD-44, OD-42, OD-43.
3. Golden set next steps: scan variants (after the vision path); real drawings and models (OD-7; public candidates in golden-data-sources.md need licence sign-off). Synthetic DWG, vector PDF and 20 STEP/STL sets exist.

## Session log

| Date | Work | Verified by |
|---|---|---|
| 2026-11-24 | Read the plan and all 98 slides. Built Phase 0 repo-side foundations: layout, contracts v0.1, eval harness, licence gate, CI script, ADRs, acceptance criteria, discrepancy log, open decisions, session harness. Every document passed two rounds of adversarial source-fidelity review | `bash scripts/ci/run_ci.sh` exit 0: ruff clean, mypy clean (16 source files), 146 tests passed, licence gate 19/19 pass; SBOM and ScanCode skipped (tools not installed). Details in [phase-0.md](phase-0.md) |
| 2026-11-24 | Recorded owner answers OD-1 to OD-9 (ADR-0001 and 0005 accepted, ADR-0006 written for OD-4). Added `.env.example`/`.env`, the Ansys import connector folder, the synthetic golden-set generator and 80 drawings, and public-source research. Fixed a dimension-text bug found by visual review | `bash scripts/ci/run_ci.sh` exit 0: ruff clean, mypy clean (22 source files), 155 tests passed, licence gate 22 pass + 1 recorded exception (numpy, OD-31). Two drawings checked visually |
| 2026-11-24 | Recorded OD-37 (OpenAI), OD-38 (multimodal API, ADR-0007), OD-10/18/21 (owner installs and creates). Generated `requirements.txt` and `requirements-dev.txt` from `uv.lock`, added a CI sync check, set `.env` for OpenAI | `run_ci.sh` exit 0: ruff, mypy (22 files), 155 tests, requirements in sync, licence gate passed. Fresh pip-only venv from `requirements-dev.txt`: 155 passed. Drift check shown to fail on an altered file |
| 2026-11-25 | Phase 1 walking skeleton: edp-kit, Data Fabric, Data Catalogue, orchestrator with stub blocks 1-8, local CLI. ADR-0008. Fixed pytest import mode (stdlib `platform` clash) | `run_ci.sh` exit 0: ruff, mypy (35 files), 183 tests, requirements in sync, licence gate 61 pass + 2 recorded exceptions. CLI run on a synthetic DXF: 8/8 blocks ok, report traced to file hash and commit |
| 2026-11-25 | Committed Phase 1 (`d6164da`). Phase 2 started: DXF Drawing Parser block (entry point), Fabric `write()`, parser evaluation suite, `--real-blocks` CLI. Fixed CRLF parsing and rounding tolerance | `run_ci.sh` exit 0: ruff, mypy (42 files), 197 tests, requirements in sync, licence gate passed. Golden suite on 80 drawings: all four Phase 2 metrics at target. The set is easy for this parser (see phase-2.md) |
| 2026-11-25 | Found and removed `robocrew`, an unplanned dependency swept into `924e4c3` (`96e293d`, with a mypy fix). Phase 3 started: dimension association, Interpretation block (holes, slots, bends, pint units, flags), labels v0.2.0 with features, Interpretation suite | `run_ci.sh` exit 0: ruff, mypy (47 files), 207 tests, requirements in sync, licence gate 65 pass. Suite: feature recall 1.0 (target 0.90), association 1.0 on the easy synthetic set |
| 2026-11-25 | Phase 3 committed (`83f7cc3`) with a root `pyproject.toml`/`uv.lock` restored to an older copy outside this session (two other Claude sessions were open on this folder); fixed in `2bc8e3a`. Console UI built: React + Vite + TS, pipeline map (React Flow, SSE), drawing sheet with source tracing, inspector, review; console API `edp_orchestrator.server`; parser records dimension text position | `run_ci.sh` exit 0: ruff, mypy (48 files), 210 tests, requirements in sync, Python licence gate 67 pass, npm licence gate 100 packages, console type check. Screenshots reviewed at 1440 and 500 px |
| 2026-11-25 | Committed console (`f755af2`). Knowledge Graph block 3: graph store (SQLite adapter), part/revision/material/feature ingestion, similar-part search, corroboration with sibling-first evidence; family golden set (labels v0.3.0); KG suite; block 2 sends low-confidence values to block 3 first (principle 3); console shows similar parts and corroboration | `run_ci.sh` exit 0: ruff, mypy (54 files), 218 tests, requirements in sync, licence gates pass. KG suite on 72 drawings: recall@3 1.0, resolved 12/24 (all agreeing cases), 0 wrong. Screenshots of a resolved and a conflicting revision |
| 2026-11-25 | OpenAI key placed in `.env` by the owner; checked without printing it | `/v1/models` 200 for gpt-5.5 and text-embedding-3-large; one 18-token Responses call; one embedding (3072 dimensions) |
| 2026-11-25 | LibreDWG 0.14 (owner download): parser prefers it; found 0.14's DXF import stores dimension rotation as oblique angle; test-DWG writer repairs it via dwgread/dwgwrite JSON; DWG set regenerated | DWG suites 1.0 (parser and interpretation, 0 flags); `run_ci.sh` exit 0: mypy 62 files, 231 tests (DWG tests run on 0.14), licence gates pass |
| 2026-11-25 | Recorded owner answers: OD-12 (all families), OD-18 (free and local CI), OD-21 (no containers), OD-39 (POC yes, identifiers removed), OD-44 (deferred), OD-49 (allowed; download still blocked), OD-10 delegated (NATS, ADR-0002 Accepted), OD-42/43 models | Docs only; LibreDWG 0.14 download tried and reset by the network |
| 2026-11-25 | Rest of Phase 2: DWG (LibreDWG 0.11 from conda-forge, separate process), vector PDF (pypdfium2), STEP and IGES (OCP), STL (trimesh); geometry schema 0.2.0 with `solids`; DXF recovery for invalid XDATA and dimension blocks; golden sets for DWG, PDF and 20 3D models; models suite; console shows samples of every format and 3D summaries | `run_ci.sh` exit 0: mypy 62 files, 231 tests, licence gates pass (matplotlib excluded by a uv override). DWG and PDF sets score as the DXF set; STEP holes exact on 20 models; STL hints 20 of 20 |

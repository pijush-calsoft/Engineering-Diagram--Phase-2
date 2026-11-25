# Progress tracker

Read this first in every session. Update it at the end of every session (see [CLAUDE.md](../../CLAUDE.md)).

**Current phases: Phase 1 in progress (walking skeleton runs locally); Phase 0 sign-off pending.** On 2026-11-24 the project owner answered OD-1 to OD-9. Two of the three exit criteria are now met locally; the remaining one needs the director's sign-off.

## Phases (plan §5)

| Phase | Name | Release | Plan duration | Status | Log |
|---|---|---|---|---|---|
| 0 | Discovery, golden data and foundations | R1 | 4 weeks | **In progress**: golden DXF set done; sign-off pending | [phase-0.md](phase-0.md) |
| 1 | Platform services and orchestrator skeleton | R1 | 4 weeks | **In progress**: walking skeleton built with local adapters (ADR-0008). Gateway and console not started | [phase-1.md](phase-1.md) |
| 2 | Drawing Parser | R1 | 5 weeks | Not started | |
| 3 | Interpretation and Knowledge Graph | R1 | 4 weeks | Not started | |
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
| 3 | Define R1 part families | **Standards decided** (ISO and ASME, OD-1). Families: working assumption = plan recommendation (OD-12), **please confirm** | |
| 4 | Plug-in contract v0.1 and artifact schemas | **Done** (v0.1.0). Deck additions not included pending OD-15 | [contracts/](../../contracts/README.md) |
| 5 | Monorepo, CI (lint, types, tests, licence scan, SBOM), container build, dev Kubernetes | **Mostly done.** uv workspace, `requirements.txt` / `requirements-dev.txt` (synced with `uv.lock`, checked in CI), provider-neutral CI script. Git repo created (OD-18). Rancher Desktop chosen as the container runtime; installing it needs admin rights ([setup guide](../setup/local-environment.md), OD-21). Open: CI provider; Syft and ScanCode not installed; no Kubernetes | [scripts/ci/](../../scripts/ci/README.md) |
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

0. Phase 1 next: Model Gateway client (OpenAI through LiteLLM; needs `OPENAI_API_KEY` and OD-43 models), console shell (React, chat panel, pipeline map from `run.*` events), MCP wrappers.
1. Confirm OD-12 (part families) and the three recorded interpretations (OD-1, OD-6, OD-9).
2. Owner actions: install WSL 2 and Rancher Desktop as administrator ([setup guide](../setup/local-environment.md)); put `OPENAI_API_KEY` in `.env`. Decisions: confirm NATS (OD-10), pick OpenAI models (OD-43), embeddings via API or local (OD-42), client data to OpenAI (OD-39), CI provider (OD-18).
3. Golden set next steps: render vector-PDF and scan variants from the synthetic DXF; sign off and ingest NIST MBE PMI and FreeCAD-library models for the 20 STEP/STL.
4. Then start Phase 1 (platform services and orchestrator skeleton, locally).

## Session log

| Date | Work | Verified by |
|---|---|---|
| 2026-11-24 | Read the plan and all 98 slides. Built Phase 0 repo-side foundations: layout, contracts v0.1, eval harness, licence gate, CI script, ADRs, acceptance criteria, discrepancy log, open decisions, session harness. Every document passed two rounds of adversarial source-fidelity review | `bash scripts/ci/run_ci.sh` exit 0: ruff clean, mypy clean (16 source files), 146 tests passed, licence gate 19/19 pass; SBOM and ScanCode skipped (tools not installed). Details in [phase-0.md](phase-0.md) |
| 2026-11-24 | Recorded owner answers OD-1 to OD-9 (ADR-0001 and 0005 accepted, ADR-0006 written for OD-4). Added `.env.example`/`.env`, the Ansys import connector folder, the synthetic golden-set generator and 80 drawings, and public-source research. Fixed a dimension-text bug found by visual review | `bash scripts/ci/run_ci.sh` exit 0: ruff clean, mypy clean (22 source files), 155 tests passed, licence gate 22 pass + 1 recorded exception (numpy, OD-31). Two drawings checked visually |
| 2026-11-24 | Recorded OD-37 (OpenAI), OD-38 (multimodal API, ADR-0007), OD-10/18/21 (owner installs and creates). Generated `requirements.txt` and `requirements-dev.txt` from `uv.lock`, added a CI sync check, set `.env` for OpenAI | `run_ci.sh` exit 0: ruff, mypy (22 files), 155 tests, requirements in sync, licence gate passed. Fresh pip-only venv from `requirements-dev.txt`: 155 passed. Drift check shown to fail on an altered file |
| 2026-11-25 | Phase 1 walking skeleton: edp-kit, Data Fabric, Data Catalogue, orchestrator with stub blocks 1-8, local CLI. ADR-0008. Fixed pytest import mode (stdlib `platform` clash) | `run_ci.sh` exit 0: ruff, mypy (35 files), 183 tests, requirements in sync, licence gate 61 pass + 2 recorded exceptions. CLI run on a synthetic DXF: 8/8 blocks ok, report traced to file hash and commit |

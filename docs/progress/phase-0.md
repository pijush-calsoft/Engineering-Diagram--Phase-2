# Phase 0 log: Discovery, golden data and foundations

| | |
|---|---|
| Plan reference | plan §6 Phase 0 (4 weeks, R1) |
| Status | In progress. Repo-side work done; exit blocked on decisions and data |
| Last updated | 2026-11-24 |

## 1. How the work was done

1. **Read first.** The plan (615 lines) and all 98 slides of the deck were read in full before anything was built. The deck text was saved as [deck-text.md](../reference/deck-text.md), with individual names on slide 86 left out.
2. **Compared.** Every place the deck disagrees with the plan is logged in [plan-vs-deck.md](../reference/plan-vs-deck.md) (D1 to D10, I1 to I4, L1 to L6). The plan is the baseline, and none of the differences was resolved silently. Each one is an entry in [open-decisions.md](../open-decisions.md).
3. **Built.** Only work that needs no human input or data was built.
4. **Checked adversarially.** Each document and module was drafted, then reviewed by an independent checker that compared it line by line with the plan and deck and ran its tests. It was then fixed and re-checked, twice. Round 1 found 40 issues (none high-severity), for example claims stronger than the source, wrong section citations, and two licence-gate bypasses. After two fix rounds, 12 low or medium items remained; these were fixed by hand and the full CI was re-run.

## 2. What was built

### 2.1 Repository layout (Phase 0 task 5)

Follows plan Appendix A. Directories for later phases hold a README that states their purpose, phase and planned stack from the plan, marked "not started". One addition: `scripts/ci/` (not in Appendix A), which holds the CI steps.

Python workspace: uv, Python >= 3.11. Members: `contracts` (edp-contracts), `eval` (edp-eval), `scripts/ci` (edp-ci). Dev tools: pytest, hypothesis, ruff, mypy. The plan names pytest and Hypothesis (§4.3). ruff and mypy are a repository choice to cover "lint, type check" (Phase 0 task 5), because the plan names no tools for those.

### 2.2 Plug-in contract v0.1 and artifact schemas (Phase 0 task 4)

- `edp_contracts.block`: the plan §3 code verbatim (`SourceLocator`, `Artifact`, `Flag`, `BlockRequest`, `BlockResult`, `Block`), plus `BlockContract` for the `GET /contract` body (accepts, produces, schema versions, as §3 describes).
- `edp_contracts.events`: Appendix B subjects. `edp_contracts.registry`: discovery over the `edp.blocks` entry point (§3).
- Artifact schemas `geometry`, `design_graph`, `cad_script`, `margins`, `report`. Every field comes from a sentence in plan Phases 2 to 6, cited in the module docstring. Fields the plan does not define are left as free-form dicts, not guessed. Exit criteria that require 100 % source locators are enforced structurally: the locator is required on each geometry entity and the source on each script parameter.
- JSON Schemas exported to `contracts/schemas/` (11 files).
- Not included, pending OD-15: the deck's `/status` and `/result` endpoints, manifest, `/v1` paths and event names.

### 2.3 Acceptance criteria (Phase 0 task 1)

[acceptance-criteria.md](../requirements/acceptance-criteria.md): criteria AC-P0 to AC-P6 and AC-R1 to AC-R3, with the plan's exact targets, measurement method and citations. It also has a traceability table showing which schema backs which criterion, and the gaps TBD-AC-1 to TBD-AC-13. Deck-only measures (slides 28, 91, 96) are listed separately as reference. Status: draft, needs director sign-off.

### 2.4 Evaluation harness (Phase 0 task 2, plan §7)

- `edp_eval.golden`: golden-dataset manifest model. The Phase 0 exit check counts at least 60 labelled drawings, and only internal or openly licensed items count, per plan Phase 0 task 2. The check also reports the 20 STEP/STL target. `client_scope` holds an opaque tag, never a client name.
- `edp_eval.metrics`: Phase 2 metrics: dimension F1, title-block accuracy, locator coverage and ECE. Matching tolerance and ECE bin count are required arguments with no default, because the plan gives neither.
- `eval/golden/manifest.example.json`: fake example items only. Real data lives in the Data Fabric (plan Appendix A) and is never committed.

### 2.5 Licence policy and CI gate (Phase 0 tasks 5 and 6, plan §9)

- [license-policy.md](../policies/license-policy.md): the policy and watch-list from plan §9, how they are enforced, and the deck-only tools that are not yet checked.
- `scripts/ci/license_policy.toml` and `edp_ci.license_gate`. The gate reads the first licence field that is present (License-Expression, then License, then classifiers), so a permissive classifier can never hide an unknown or GPL expression. It fails on GPL, AGPL, SSPL, BUSL and RSAL, and on unknown licences. An `[exceptions]` entry can never clear metadata text that names a denied licence.
- `scripts/ci/run_ci.sh`: ruff, mypy, pytest, the licence gate, then the Syft SBOM and ScanCode scan when those tools are installed. Otherwise it prints a clear SKIPPED line.

### 2.6 ADRs (Phase 0 task 7)

ADR-0001 orchestrator, 0002 event bus, 0003 graph store, 0004 object storage and dataset versioning, 0005 model hosting. All are **Proposed**. Each one records the plan's choice, the alternative the plan lists, and the deck's position. ADR-0006 to 0008 are reserved (OD-19).

### 2.7 Harness and reference docs

[CLAUDE.md](../../CLAUDE.md) holds the session rules and the update routine. Also: [docs/README.md](../README.md), this log, [PROGRESS.md](PROGRESS.md), [open-decisions.md](../open-decisions.md) (OD-1 to OD-36) and [plan-vs-deck.md](../reference/plan-vs-deck.md).

## 3. Verification (2026-11-24)

```text
$ bash scripts/ci/run_ci.sh
=== Lint (ruff) ===              All checks passed!
=== Type check (mypy) ===        Success: no issues found in 16 source files
=== Tests (pytest) ===           146 passed
=== Licence gate (plan §9) ===   19 distributions checked: 19 pass, 0 warn, 0 exception, 0 fail. Gate PASSED.
=== SBOM (Syft) ===              SKIPPED: syft not installed
=== Licence scan (ScanCode) ===  SKIPPED: scancode not installed
```

Test split: contracts 17, eval and licence gate the rest. The gate's PASS for `typing_extensions` depends on `PSF-2.0` being allowed, which is still a proposal (OD-31).

## 4. Pending for Phase 0 exit

| Item | Blocked on |
|---|---|
| Director sign-off of part families and metrics | OD-1, OD-12; review of acceptance-criteria.md |
| 60 labelled drawings and 20 STEP/STL models in Label Studio | OD-7, OD-17; Label Studio setup |
| CI running on a provider; git repository | OD-18 |
| SBOM and first ScanCode scan | Installing Syft and ScanCode on CI |
| Container build and dev Kubernetes | OD-21 (Docker missing) |
| Hardware sizing | OD-20, OD-23 |
| ADR-0006 to 0008 topics; ADRs moved from Proposed to Accepted | OD-19; owner decisions OD-9 to OD-11 |
| Licence policy additions | OD-31 to OD-36 |

---

## 5. Session 2 (2026-11-24): owner answers and the golden set

### 5.1 Decisions recorded

The project owner answered OD-1 to OD-9. Each answer is quoted in [open-decisions.md](../open-decisions.md). Three answers were ambiguous, and the recorded reading is marked there for confirmation:

| ID | Answer | Recorded as | Effect |
|---|---|---|---|
| OD-1 | "try both" | Both ISO and ASME drawing standards | Generator has `iso` and `asme` profiles. Part families not named, so OD-12 is a working assumption: the plan's recommended families |
| OD-2 | "we will run locally (create .env file)" | Local run | `.env.example` (committed) and `.env` (git-ignored) |
| OD-3 | "all solver" | CalculiX, Code_Aster, FEniCSx and Ansys result import | `blocks/b6_solvers/ansys_import/` added; README lists all four |
| OD-4 | "you decide" | Open formats in the Data Fabric plus a Git branch and PR | [ADR-0006](../adr/0006-r2-write-back-targets.md) |
| OD-5 | "api calls only no fine tuning or local llm" | Hosted APIs through LiteLLM; no vLLM, no fine-tuning | [ADR-0005](../adr/0005-model-hosting.md) accepted, amended. Follow-ups OD-37 to OD-39 |
| OD-6 | "we will use llms as judge" | LLM judges review reports; the deterministic fact check and human approval of write-backs stay | Follow-up OD-40 (sign-off wording) |
| OD-7 | "no golden data set, we need to create or have one if available" | Build a synthetic set; search for public sets | See 5.2 and 5.3 |
| OD-8 | "take time to complete all" | Plan phases are the baseline | Tracker unchanged |
| OD-9 | "yes" | Python LangGraph + Temporal (the plan's option) | [ADR-0001](../adr/0001-orchestrator.md) accepted |

### 5.2 Synthetic golden set

- `eval/src/edp_eval/synth/` holds `profiles.py`, `parts.py`, `labels.py`, `dxf_writer.py` and the CLI. It uses ezdxf (plan §4.2 block 1), added to `edp-eval`.
- 80 drawings generated with seed 2026: 20 each of ISO plate, ISO bracket, ASME plate and ASME bracket. Each has a `.labels.json` and a manifest entry with provenance `internal`. `phase0_exit_check()` passed with 80 labelled drawings.
- **A bug was caught in visual review.** The ezdxf `EZDXF` and `EZ_RADIUS` dimension styles ship with `dimlfac = 100`, so the first set displayed 100× the true values (for example "18000" for 180 mm). The measured geometry was right, so the first self-check missed it. The fix sets `dimlfac = 1`, and `verify()` now also checks the displayed dimension text. A regression test covers it. The set was regenerated and two drawings were re-checked by eye.
- Repeated hole positions are now dimensioned once each.

### 5.3 Public sources

[golden-data-sources.md](../reference/golden-data-sources.md): no public set gives 60 to 100 commercially licensed drawings with dimension ground truth. Best candidates for the 20 STEP/STL models: NIST MBE PMI test cases ("can be used without any restrictions") and FreeCAD-library (CC-BY 3.0). Nothing has been downloaded; licence sign-off comes first.

### 5.4 Licence gate

ezdxf pulls in numpy, whose metadata says `BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0`. 0BSD, Zlib and CC0-1.0 are not named in plan §9, so the gate failed as designed. A scoped `[exceptions]` entry for numpy quotes the metadata; sign-off is pending as OD-31.

### 5.5 Verification

```text
$ bash scripts/ci/run_ci.sh
Lint (ruff)        All checks passed!
Type check (mypy)  Success: no issues found in 22 source files
Tests (pytest)     155 passed
Licence gate       23 distributions checked: 22 pass, 0 warn, 1 exception, 0 fail. Gate PASSED.
SBOM, ScanCode     SKIPPED (tools not installed)
```

### 5.6 Still pending for Phase 0

- Confirm OD-12 and the readings of OD-1, OD-6 and OD-9.
- Vector-PDF and scan slices of the golden set; the 20 STEP/STL models.
- OD-18 (git, CI), OD-21 (Docker), OD-31 to OD-41.
- Director review of the acceptance criteria.

## 6. Session 3 (2026-11-24): provider, vision and requirements

| ID | Answer | Recorded as |
|---|---|---|
| OD-37 | "open AI api key we will be using" | Provider OpenAI; `OPENAI_API_KEY` slot in `.env`; models open (OD-43) |
| OD-38 | "we will be using Multimodal LLm using api" | OCR, symbols, GD&T, title blocks and notes through a multimodal model over the API ([ADR-0007](../adr/0007-vision-via-multimodal-api.md)). Plan Phase 2 task 4 (detector fine-tune) dropped. Embeddings not covered (OD-42) |
| OD-10, OD-18, OD-21 | "we will install, create and requirements.txt" | Owner installs Docker and creates the git repo. Event bus not named, so NATS JetStream (plan) is the working choice, pending confirmation. `requirements.txt` created |

Work done:

- `requirements.txt` (runtime) and `requirements-dev.txt` (with test and lint tools), generated with `uv export` from `uv.lock`. Workspace packages are editable installs (`-e ./contracts`, `-e ./eval`, `-e ./scripts/ci`).
- New CI step: both files must match `uv.lock`. It was tested against an altered copy and failed as expected.
- `.env` and `.env.example`: provider set to `openai`, key slot renamed to `OPENAI_API_KEY`. Edited by script without printing any value; the key is still empty.
- ADR-0005 (provider), ADR-0002 (working choice note), ADR-0007 (new), ADR index, block 1 and gateway READMEs, CLAUDE.md, README.

Verification:

```text
bash scripts/ci/run_ci.sh: ruff passed; mypy 22 files clean; 155 passed; requirements match uv.lock; licence gate PASSED (22 pass, 1 exception)
Fresh venv, plain pip: pip install -r requirements-dev.txt, then pytest: 155 passed
```

## 7. Session 4 (2026-11-24): git repository and container runtime

- **Git (OD-18):** `git init -b main`. Identity set for this repository only (`git config --local`). `.gitattributes` keeps `*.sh` at LF, because the machine has `core.autocrlf=true`. Ignore rules checked with `git status --ignored`: `.env`, `.venv/`, caches and `eval/golden/data/` are excluded. A pattern scan of the files to be committed found no keys. Initial commit made.
- **Container runtime (OD-21):** the session had no admin rights and the machine had no WSL, so nothing was installed. `winget show` reported Docker Desktop as "Proprietary" (Docker Subscription Service Agreement), and Rancher Desktop and Podman Desktop as Apache-2.0. The owner chose **Rancher Desktop**. Steps to run as administrator: [setup/local-environment.md](../setup/local-environment.md).

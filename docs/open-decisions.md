# Open decisions

These are decisions the plan, the deck or the repo setup leaves open. The code here does not settle any of them on its own. Once one is decided, record the answer, the owner and the date here, and add an ADR in [adr/](adr/) if it changes architecture.

Status values: **Open**, **Decided**, **Superseded**.

## From the plan (§11, questions for the director)

| ID | Question | Status | Notes |
|---|---|---|---|
| OD-1 | Which part families and drawing standards (ISO, ASME) matter most for the first pilot? | Decided 2026-11-24 (project owner) | Answer: "try both". Recorded as: **both ISO and ASME** drawing standards. Part families were not named in the answer; see OD-12 |
| OD-2 | Is the platform hosted by Calsoft, deployed into client environments, or both? | Decided 2026-11-24 (project owner) | Answer: "we will run locally (create .env file)". Local configuration lives in `.env` (not committed) with `.env.example` as the template. GPL tools stay isolated anyway (plan §9 policy is unchanged) |
| OD-3 | Which solvers do target clients already trust? | Decided 2026-11-24 (project owner) | Answer: "all solver". Recorded as: connectors for every solver named in plan and deck: CalculiX, Code_Aster, FEniCSx (plan §4.2 block 6) and Ansys result import (deck slides 65, 90). Ansys import needs an Ansys licence (deck slide 90); still a prerequisite |
| OD-4 | Which PLM or document systems are the first write-back targets in R2? | Decided 2026-11-24 (project owner) | Answer: "you decide". Decided in [ADR-0006](adr/0006-r2-write-back-targets.md): open formats in the Data Fabric plus a Git branch and PR for scripts; PLM connectors per engagement |
| OD-5 | GPU budget for self-hosted models; are hosted model APIs allowed for non-client data? | Decided 2026-11-24 (project owner) | Answer: "api calls only no fine tuning or local llm". See [ADR-0005](adr/0005-model-hosting.md). Follow-ups OD-37, OD-38, OD-39 |
| OD-6 | Who signs off engineering results in reports, and what wording is required? | Decided 2026-11-24 (project owner), with a follow-up | Answer: "we will use llms as judge". Recorded as: LLM judges review reports (faithfulness, hallucination; plan Phase 6 task 3 already uses DeepEval). The deterministic fact check stays the blocking gate (plan Phase 6 task 3), and human approval before any write-back stays (plan principle 5), because the answer did not remove them. Report wording is still open: OD-40 |
| OD-7 | Is there an internal set of drawings usable for the golden dataset without client restrictions? | Decided 2026-11-24 (project owner) | Answer: "no golden data set, we need to create or have one if available". Action: a synthetic drawing generator with exact ground truth (`edp_eval.synth`), plus a search for openly licensed public sets ([golden-data-sources.md](reference/golden-data-sources.md)) |

## From comparing the plan with the deck ([plan-vs-deck.md](reference/plan-vs-deck.md))

| ID | Question | Status | Ref |
|---|---|---|---|
| OD-8 | Which R1 timeline is the baseline: plan Phases 0 to 6 (gate 24 May 2027) or deck 8 weeks / 4 sprints? | Decided 2026-11-24 (project owner) | Answer: "take time to complete all". Recorded as: the **plan's phases** are the baseline, not the 8-week deck plan. D1, D2 |
| OD-9 | Controller and orchestrator: Python LangGraph + Temporal (plan) or Java Spring Boot Controller (deck)? | Decided 2026-11-24 (project owner) | Answer: "yes". Recorded as confirming the plan's **Python LangGraph + Temporal** ([ADR-0001](adr/0001-orchestrator.md)). Correct this if "yes" meant the Java Controller. D3, D4 |
| OD-10 | Event bus: NATS JetStream (plan) or Kafka (deck)? | **Working choice: NATS JetStream, please confirm** | Answer: "we will install" (OD-10, OD-18 and OD-21 were answered together), with no broker named. The plan's NATS JetStream is used until confirmed; [ADR-0002](adr/0002-event-bus.md) stays Proposed. D5 |
| OD-11 | Model hosting: self-hosted vLLM + LiteLLM (plan) or in-house plus AWS Bedrock (deck)? | Decided 2026-11-24 (project owner) via OD-5 | Hosted APIs only, through the LiteLLM proxy. Provider open: OD-37. D6 |
| OD-12 | R1 domain: prismatic machined parts and sheet-metal brackets (plan) or the seat-structure pack (deck)? | **Working assumption, please confirm** | Not answered directly. The synthetic golden set uses the plan's families (prismatic plates and sheet-metal brackets). The deck's seat recliner bracket is a sheet-metal bracket, so it is covered. D7 |
| OD-13 | Which feature list is R1 scope: plan §1 table or deck F-01 to F-34? | Open | D8 |
| OD-14 | Where are the "In/Out lines" per block that Phase 0 task 1 refers to? The deck in this repo has none | Open | plan-vs-deck §5 |
| OD-15 | Plug-in contract: keep plan §3 (`/run`, `/health`, `/contract`, Appendix B events) or add deck items (`/status`, `/result`, manifest, `/v1` paths, deck event names)? | Open | I1 to I4 |
| OD-16 | Surrogate method: Gaussian process family (plan) or PINN / ROM (deck)? | Open | D9 |
| OD-17 | Golden data source: internal or openly licensed (plan) or the customer's drawing set (deck)? | Decided 2026-11-24 (project owner) via OD-7 | Internal (synthetic) and openly licensed, as in the plan. D10 |

## From repository setup

| ID | Question | Status | Notes |
|---|---|---|---|
| OD-18 | CI provider and git hosting | Decided 2026-11-24 (project owner), in part | Git repository created (branch `main`, repo-local identity, initial commit). `requirements.txt` and `requirements-dev.txt` are generated from `uv.lock` and checked in CI. **CI provider and remote hosting still open.** CI steps are in `scripts/ci/run_ci.sh`, which any provider can call |
| OD-19 | Topics for ADR-006 to ADR-008 | Decided 2026-11-25 | Used for OD-4 (ADR-0006), OD-38 (ADR-0007) and the local-first adapters (ADR-0008) |
| OD-20 | Hardware sizing inputs: GPU for the VLM and code model, CPU cores for meshing and solvers | Decided 2026-11-24 (project owner) via OD-5 and OD-38, in part | **No GPU needed**: all LLM and vision work is through the OpenAI API. CPU cores and memory for meshing and solvers on the local machine are still to size in Phase 5 |
| OD-21 | Container runtime on the development machine | Decided 2026-11-24 (project owner) | **Rancher Desktop** (Apache-2.0), with dockerd (moby) for the `docker` CLI. Docker Desktop was not chosen because it is proprietary (Docker Subscription Service Agreement). Install needs admin rights and WSL 2: steps in [setup/local-environment.md](setup/local-environment.md). **Not installed yet** |

## From the deck (slide 91, "Decisions needed before Sprint 1")

These are listed with the owner role the deck gives. They overlap with the items above where noted.

| ID | Decision | Deck owner role | Overlaps |
|---|---|---|---|
| OD-22 | UI engineer assigned for the web screens | Managing team | |
| OD-23 | GPU type, count and hosting; CPU solver nodes | Infrastructure lead | OD-5, OD-20 |
| OD-24 | Models to host, with their licences | Platform lead | OD-11, plan §9 |
| OD-25 | Certificate authority and revocation process | Security lead | Plan picks step-ca (§4.1) |
| OD-26 | Sample drawing set for the test corpus | Customer architect | OD-7, OD-17 |
| OD-27 | Solver choice and licences (CalculiX, Ansys import) | Delivery lead | OD-3 |
| OD-28 | Reference load cases and standards (FMVSS, ECE) | Customer CAE lead | OD-1, OD-12 |
| OD-29 | Report templates, audiences and sign-off roles | Customer design lead | OD-6 |
| OD-30 | First Release 2 pilot: seat or exhaust | Sponsor | |

## From Phase 0 work: licence policy (needs the accountable owner and legal)

| ID | Question | Status | Notes |
|---|---|---|---|
| OD-31 | Approve `PSF-2.0` and `ISC` as allowed licences, and `0BSD`, `Zlib` and `CC0-1.0` (numpy). None is named in plan §9 | Open | The gate passes `typing_extensions` (PSF-2.0, a pydantic dependency) under this proposal. `numpy` (needed by ezdxf) passes through a scoped `[exceptions]` entry that quotes its metadata. [license-policy.md](policies/license-policy.md) §1 |
| OD-32 | Confirm how unversioned classifiers are treated: "BSD License" is allowed, while "Apache Software License" and "Python Software Foundation License" fail as unknown | Open | Plan §9 says "BSD" without a variant and names Apache 2.0 only |
| OD-33 | Confirm the denied ids derived from the §9 watch-list (SSPL, BUSL, RSAL variants, GPL-1.0) | Open | [license-policy.md](policies/license-policy.md) §6 |
| OD-34 | Confirm `OCCT-exception-1.0` as the only accepted SPDX `WITH` exception | Open | Plan §4.2 says only "OCCT is LGPL 2.1 with exception" |
| OD-35 | Classify EPL 2.0 (Eclipse Ditto, R3). It is not in the §9 policy classes | Open | Plan §4.2 block "Digital twin" |
| OD-36 | How the §9 LGPL rule ("allowed when used as a library without modification") applies to LGPL software the plan lists as a service, e.g. Ceph RGW | Open | [ADR-0004](adr/0004-object-storage.md) |

## From the owner's answers of 2026-11-24

| ID | Question | Status | Notes |
|---|---|---|---|
| OD-37 | Which hosted model API provider(s)? | Decided 2026-11-24 (project owner) | Answer: "open AI api key we will be using". Provider: **OpenAI**; key in `.env` as `OPENAI_API_KEY`. Model names: OD-43. Review OpenAI terms and data-usage policy before use (OD-39) |
| OD-38 | Does "no local LLM" also rule out local non-LLM models: the symbol detector (RT-DETR or D-FINE, plan Phase 2 task 4), OCR (PaddleOCR or docTR) and embeddings (bge-m3 or nomic-embed, plan Phase 3)? | Decided 2026-11-24 (project owner), in part | Answer: "we will be using Multimodal LLm using api". OCR, symbols, GD&T, title blocks and notes go to a multimodal model over the API ([ADR-0007](adr/0007-vision-via-multimodal-api.md)); Phase 2 task 4 (detector fine-tune) is dropped. **Embeddings not covered: OD-42** |
| OD-39 | May client drawings be sent to external model APIs, and under what conditions? | Open | Principle 7 (plan §2.3). Until a client's SOW allows it, only internal or openly licensed data goes to external APIs |
| OD-40 | Report sign-off wording, and who, if anyone, signs engineering results. LLM judges review; does a named engineer still sign? | Open | Plan §1 excludes "certification of solver results for regulatory sign-off"; plan §10 risk 3 mitigation is "engineer sign-off language in reports" |
| OD-41 | Which ISO and ASME conventions the synthetic drawings follow in detail (projection method, dimension style, units, general tolerance note) | Open | The generator implements both as configurable profiles; see [eval/README.md](../eval/README.md) |
| OD-42 | Knowledge Graph embeddings (plan Phase 3: bge-m3 / nomic-embed, local): through the OpenAI API or local? | Open | Not covered by the OD-38 answer. "No local LLM" (OD-5) does not clearly cover embedding models |
| OD-43 | Which OpenAI models for text, vision, code generation and LLM-as-judge? | Open | `.env` slots `EDP_LLM_MODEL_TEXT`, `_VISION`, `_CODE`, `_JUDGE` are blank. The nightly gateway benchmark (plan Phase 1, §7 Gateway row) can inform the choice |
| OD-44 | Virus scanner for uploads (plan Phase 1: "virus and type check") | Open | Type check from content is built in `edp_fabric`; no scanner chosen. Plan and deck name none |
| OD-45 | Geometric coincidence tolerance for dimension association and feature rules | Open | `REL_TOL = 1e-6` (relative) in `edp_b2_interpretation.recognise`: exact for CAD-written files. Real drawings may need a looser, possibly per-client value (plan Phase 2 risks: "per-client drafting profiles stored as configuration") |

## Detail items tracked in their own documents

These are "not specified in plan or deck; TBD in Phase 0" items. They live next to the text they affect, so they are not copied here. Close them in that document and note the decision there.

| Where | IDs | Topics |
|---|---|---|
| [requirements/acceptance-criteria.md](requirements/acceptance-criteria.md) §12 | TBD-AC-1 to TBD-AC-13 | Scoring of DWG/STEP/STL, meaning of a "valid" locator, curated set size, repair attempts and sandbox limits, surrogate error definition, DeepEval thresholds, pilot targets, R2 case set, R3 strain tolerance, load-test concurrency, measurement methods, deck promotion gate |
| [eval/README.md](../eval/README.md), open items | (unnumbered) | Dimension matching algorithm and `value_tol`; what counts as "labelled"; whether the internal/open rule covers the 20 STEP/STL models; ECE bin count; DWG and 3D target column; "60 to 100" reading; label export format; empty predictions; PR fast subset; "valid" locator |
| [policies/license-policy.md](policies/license-policy.md) §6 | (unnumbered) | Running the first ScanCode scan, installing Syft and ScanCode on CI, Trivy, licence checks for deck-only tools |
| [adr/](adr/README.md) | Open items section in each ADR | Per-ADR questions |

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
| OD-5 | GPU budget for self-hosted models; are hosted model APIs allowed for non-client data? | Decided 2026-11-24 (project owner), confirmed 2026-11-25 | Answer: "api calls only no fine tuning or local llm"; confirmed 2026-11-25: "only api of openai". See [ADR-0005](adr/0005-model-hosting.md). This replaces the plan's self-hosted models, including the block 4 code model (plan Phase 4 task 2: Qwen-Coder via vLLM), with the OpenAI API. Follow-ups OD-37, OD-38, OD-39 |
| OD-6 | Who signs off engineering results in reports, and what wording is required? | Decided 2026-11-24 (project owner), with a follow-up | Answer: "we will use llms as judge". Recorded as: LLM judges review reports (faithfulness, hallucination; plan Phase 6 task 3 already uses DeepEval). The deterministic fact check stays the blocking gate (plan Phase 6 task 3), and human approval before any write-back stays (plan principle 5), because the answer did not remove them. Report wording is still open: OD-40 |
| OD-7 | Is there an internal set of drawings usable for the golden dataset without client restrictions? | Decided 2026-11-24 (project owner) | Answer: "no golden data set, we need to create or have one if available". Action: a synthetic drawing generator with exact ground truth (`edp_eval.synth`), plus a search for openly licensed public sets ([golden-data-sources.md](reference/golden-data-sources.md)) |

## From comparing the plan with the deck ([plan-vs-deck.md](reference/plan-vs-deck.md))

| ID | Question | Status | Ref |
|---|---|---|---|
| OD-8 | Which R1 timeline is the baseline: plan Phases 0 to 6 (gate 24 May 2027) or deck 8 weeks / 4 sprints? | Decided 2026-11-24 (project owner) | Answer: "take time to complete all". Recorded as: the **plan's phases** are the baseline, not the 8-week deck plan. D1, D2 |
| OD-9 | Controller and orchestrator: Python LangGraph + Temporal (plan) or Java Spring Boot Controller (deck)? | Decided 2026-11-24 (project owner) | Answer: "yes". Recorded as confirming the plan's **Python LangGraph + Temporal** ([ADR-0001](adr/0001-orchestrator.md)). Correct this if "yes" meant the Java Controller. D3, D4 |
| OD-10 | Event bus: NATS JetStream (plan) or Kafka (deck)? | Decided 2026-11-25 (delegated by the project owner: "its upto u") | **NATS JetStream**, the plan's choice (plan §4.1); [ADR-0002](adr/0002-event-bus.md) Accepted. The POC keeps the in-process bus of [ADR-0008](adr/0008-local-first-adapters.md) behind the same interface; a NATS adapter is added when blocks run as separate processes. NATS needs no container (OD-21): the server is a single native program. D5 |
| OD-11 | Model hosting: self-hosted vLLM + LiteLLM (plan) or in-house plus AWS Bedrock (deck)? | Decided 2026-11-24 (project owner) via OD-5 | Hosted APIs only, through the LiteLLM proxy. Provider open: OD-37. D6 |
| OD-12 | R1 domain: prismatic machined parts and sheet-metal brackets (plan) or the seat-structure pack (deck)? | Decided 2026-11-25 (project owner) | Answer: "try to incorporate all". Recorded as **both**: the plan's prismatic machined parts and sheet-metal brackets (plan §6 Phase 0 task 3), and the deck's seat-structure pack, seat frame and recliner bracket with FMVSS and ECE load cases (deck slides 10, 20, 34, 50). Castings and assemblies are not in either option and stay deferred (plan Phase 0 task 3, §10 risk 11). Note: the deck's PoC is "one seat assembly", so the seat frame touches the deferred assembly scope; it is handled part by part until the owner says otherwise. Golden data for the seat frame does not exist yet. D7 |
| OD-13 | Which feature list is R1 scope: plan §1 table or deck F-01 to F-34? | Open | D8 |
| OD-14 | Where are the "In/Out lines" per block that Phase 0 task 1 refers to? The deck in this repo has none | Open | plan-vs-deck §5 |
| OD-15 | Plug-in contract: keep plan §3 (`/run`, `/health`, `/contract`, Appendix B events) or add deck items (`/status`, `/result`, manifest, `/v1` paths, deck event names)? | Open | I1 to I4 |
| OD-16 | Surrogate method: Gaussian process family (plan) or PINN / ROM (deck)? | Open | D9 |
| OD-17 | Golden data source: internal or openly licensed (plan) or the customer's drawing set (deck)? | Decided 2026-11-24 (project owner) via OD-7 | Internal (synthetic) and openly licensed, as in the plan. D10 |

## From repository setup

| ID | Question | Status | Notes |
|---|---|---|---|
| OD-18 | CI provider and git hosting | Decided 2026-11-25 (project owner) | Answer: "use whatever is available free or opensource". The repository has no remote, so CI stays local: `scripts/ci/run_ci.sh`, run before every commit (CLAUDE.md rule). No git hook: on 2026-11-25 the owner chose to run CI manually for now ("lets do it manually for now"). When a remote is added, the same script runs in that host's free CI. Syft and ScanCode (both open source) are still not installed: Syft ships as a GitHub release file, which this network blocks (OD-49) |
| OD-19 | Topics for ADR-006 to ADR-008 | Decided 2026-11-25 | Used for OD-4 (ADR-0006), OD-38 (ADR-0007) and the local-first adapters (ADR-0008) |
| OD-20 | Hardware sizing inputs: GPU for the VLM and code model, CPU cores for meshing and solvers | Decided 2026-11-24 (project owner) via OD-5 and OD-38, in part | **No GPU needed**: all LLM and vision work is through the OpenAI API. CPU cores and memory for meshing and solvers on the local machine are still to size in Phase 5 |
| OD-21 | Container runtime on the development machine | Decided 2026-11-25 (project owner); supersedes the 2026-11-24 Rancher Desktop choice | Answer: "no need for container". No container runtime for the POC. GPL tools (LibreDWG, and later Gmsh, CalculiX, Code_Aster, OpenSCAD) run as separate local processes, which plan §9 allows ("separate processes or containers"). Platform services stay on the local adapters of [ADR-0008](adr/0008-local-first-adapters.md). Out of POC scope: container builds, Kubernetes, Helm, Argo CD, OpenTofu (`deploy/`) |

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
| OD-31 | Approve `PSF-2.0` and `ISC` as allowed licences, and `0BSD`, `Zlib` and `CC0-1.0` (numpy), `OFL-1.1` (console fonts), `CNRI-Python` (regex, via LiteLLM), and the scoped exceptions for `sqlite-vec`, `pypdfium2` (bundled FreeType under the FTL), `python-dateutil`, `regex`, `tiktoken` and `tokenizers`. None is named in plan §9 | Open | The gate passes `typing_extensions` (PSF-2.0, a pydantic dependency) under this proposal. `numpy` (needed by ezdxf) passes through a scoped `[exceptions]` entry that quotes its metadata. [license-policy.md](policies/license-policy.md) §1 |
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
| OD-39 | May client drawings be sent to external model APIs, and under what conditions? | Decided 2026-11-25 (project owner), for the POC | Answer: "yes, we can expose for now as initially we are using this for poc". Drawings may go to the OpenAI API during the POC. **Organisation policy still applies and is not overridden by this answer:** no client-identifying information in prompts to external systems, and no credentials or personal data. So the Model Gateway must remove client names and identifying title-block fields (company, drawn-by, approver) before a call; the plan's gateway guardrails name Presidio for this (plan Phase 1, Model Gateway row). Revisit before any use beyond the POC |
| OD-40 | Report sign-off wording, and who, if anyone, signs engineering results. LLM judges review; does a named engineer still sign? | Open | Plan §1 excludes "certification of solver results for regulatory sign-off"; plan §10 risk 3 mitigation is "engineer sign-off language in reports" |
| OD-41 | Which ISO and ASME conventions the synthetic drawings follow in detail (projection method, dimension style, units, general tolerance note) | Open | The generator implements both as configurable profiles; see [eval/README.md](../eval/README.md) |
| OD-42 | Knowledge Graph embeddings (plan Phase 3: bge-m3 / nomic-embed, local): through the OpenAI API or local? | Decided 2026-11-25 (project owner) | Answer: "text-embedding-3-large", through the OpenAI API (`EDP_EMBEDDING_MODEL`). Differs from the plan's local bge-m3 / nomic-embed; client data to the API still depends on OD-39 |
| OD-43 | Which OpenAI models for text, vision, code generation and LLM-as-judge? | Decided 2026-11-25 (project owner) | Answer: "you can use model - gpt-5.5". Recorded for all four roles (`EDP_LLM_MODEL_TEXT`, `_VISION`, `_CODE`, `_JUDGE`); one model for every role is our reading of the answer. The nightly gateway benchmark (plan Phase 1, §7 Gateway row) can still compare models later |
| OD-44 | Virus scanner for uploads (plan Phase 1: "virus and type check") | Decided 2026-11-25 (project owner): deferred | Answer: "no need for now". No virus scanner in the POC; the content type check in `edp_fabric` stays |
| OD-45 | Geometric coincidence tolerance for dimension association and feature rules | Open | `REL_TOL = 1e-6` (relative) in `edp_b2_interpretation.recognise`: exact for CAD-written files. Real drawings may need a looser, possibly per-client value (plan Phase 2 risks: "per-client drafting profiles stored as configuration") |
| OD-46 | npm registry access: `registry.npmjs.org` resets the connection on this network | Open | `console/.npmrc` uses `registry.yarnpkg.com` (same packages). Confirm this is acceptable, or provide the company proxy or mirror |
| OD-47 | Similar-part descriptor and corroboration policy: equal-weight score over feature counts, overall dimensions and feature parameters; sibling revisions decide; confidence 0.7 + 0.1 per agreeing part | Open | Built as starting choices in `edp_b3_knowledge_graph`; they meet the Phase 3 targets on synthetic families. Confirm on real drawings; embeddings (OD-42) would change the score |
| OD-48 | Time limit for DWG conversion | Open | `EDP_DWG2DXF_TIMEOUT`, default 120 s in `edp_b1_parser.dwg`. A starting value, not from the plan; deck slide 43 says limits are settings with defaults from Phase 0 |
| OD-49 | LibreDWG version, source and isolation | Decided 2026-11-25 (project owner) | Answer: "allowed". The network still blocks GitHub release files, so the owner downloaded the official `libredwg-0.14-win64.zip` and extracted it to `tools/libredwg-0.14-win64/` (git-ignored); `dwg2dxf --version` reports 0.14. The parser now prefers 0.14 and falls back to 0.11 (conda-forge). Findings: 0.14 cannot read DWGs written by 0.11 (buffer overflows), while 0.11 reads DWGs written by 0.14, so 0.11's DWG writer is the faulty one; 0.14's DXF import stores a dimension's rotation as its oblique angle, which the test-DWG writer repairs through `dwgread`/`dwgwrite` JSON. The zip's `.sig` signature was not checked (the zip was extracted before it reached this session). Runs as a separate process (OD-21). ODA File Converter only after legal review (plan §9) |
| OD-50 | Gateway limits: spending budget, call timeout, retry count | Open | Plan §4.1 names "budgets" and "fallbacks" for LiteLLM but gives no values. `EDP_LLM_BUDGET_USD` blank = no limit; `EDP_LLM_TIMEOUT_S` and `EDP_LLM_MAX_RETRIES` blank = LiteLLM defaults. Spend so far: `python -m edp_gateway usage` |
| OD-51 | Gateway guardrails for the POC: Presidio and NeMo Guardrails (plan §4.1) or the built-in rules | Open | Built: deterministic redaction (`EDP_REDACT_TERMS`, e-mails, phone numbers of 8+ digits, values after COMPANY, CUSTOMER, CLIENT, VENDOR, SUPPLIER, DRAWN, CHECKED, APPROVED, DESIGNED, ENGINEER, AUTHOR labels) and an injection guard (untrusted text as `<data>`, pattern screening that flags for review). Presidio needs a spaCy model download; NeMo Guardrails was not evaluated. **Client images are refused** until a title-block masking step exists. Both lists are starting choices, not plan values ([ADR-0009](adr/0009-model-gateway-in-process.md)) |
| OD-52 | Scan clean-up and synthetic-scan settings | Open | Starting choices, not plan values: 3-pixel median filter, deskew window 10 degrees, long line = 25 % of the shorter side (`edp_b1_parser.scan`); test scans at 150 DPI, up to 2 degrees skew, 3-pixel blur, noise sigma 6 (`edp_eval.synth.scan`). Real scans should set them |
| OD-53 | Cost and effort of vision calls | Open | About 0.10 USD and 30 to 120 s per scanned page with gpt-5.5, mostly reasoning tokens. A lower reasoning effort, smaller images or tiling change cost and accuracy; none is set by the plan. Measured spend: `python -m edp_gateway usage` |
| OD-54 | Which runs may enter the Knowledge Graph | Open | Today every run is ingested. Found 2026-11-25 in the console: a scan whose part number was misread ("EDR-SYN-0000" for EDP-SYN-0000) became a new part, and 3D models without a part number become "unidentified" parts, so similar-part lists fill with them. Options: ingest only reviewed runs, or only fields above a confidence, or keep everything but hide unidentified parts. The plan does not say |

## From the construction slice (2026-11-26)

| ID | Question | Status | Notes |
|---|---|---|---|
| OD-55 | Domain for the first end-to-end slice | Decided 2026-11-26 (team direction: "we are working in construction diagrams") | **Construction**, starting with steel column base plates: the simplest construction part that runs the whole loop. It is neither the plan's generic families nor the deck's seat pack (D7, OD-12); both stay. Construction is not in the deck's target industries (deck slide 93) or requirements matrix (deck slide 97). Confirm with the accountable owner that this is a pilot domain and not a scope change |
| OD-56 | Load values in `domain_packs/construction/load_cases.json` | Open | The one load case (100 kN uplift under an HEA 200 column) is **illustrative**, so the pipeline can run. It is flagged in every margin run (`ILLUSTRATIVE_LOAD`) and in every report. Project load combinations must come from the structural engineer. The modelling of the case (bores fixed, equal nodal forces over the footprint, no bolts, washers or grout) is also a starting choice to review |
| OD-57 | Mesh size rule and convergence | Open | Block 6 uses half the smaller of plate thickness and smallest hole as the maximum element size, and a quarter of that as the minimum. Starting values, not plan values. Plan §7 tracks mesh convergence with no target; no convergence study is run yet, and a peak at a fixed bore edge is mesh-sensitive |
| OD-58 | Time limits for generated scripts and solver runs | Open | `EDP_SANDBOX_TIMEOUT_S` default 120 s (the value in the deck's AD-1 mock-up, slide 79) and `EDP_SOLVER_TIMEOUT_S` default 1800 s (the CalculiX adapter spec example, deck slide 48). Both are deck illustrations, not decided limits (TBD-AC-4). The sandbox is a separate process, not a container without network (OD-21) |
| OD-59 | Licence exceptions for CadQuery and its dependencies | Open, extends OD-31 | `cadquery`, `multimethod`, `trame-common` (Apache-2.0 texts with metadata the gate cannot map) and `llvmlite` (BSD-2-Clause and Apache-2.0 WITH LLVM-exception). Each reviewed 2026-11-26 with the reason in `scripts/ci/license_policy.toml`. `casadi` is LGPL (warning, unmodified library). CalculiX (GPL-2.0-or-later) and Gmsh (GPL) run only as separate processes from environments outside the workspace |
| OD-60 | Domain pack ownership and how a run chooses its pack | Open | [ADR-0010](adr/0010-domain-packs-and-pass-through.md): `params["domain_pack"]`, CLI `--domain-pack`, console `domain_pack` query parameter (`con-*` samples default to construction). The deck puts the domain in the run spec (deck slide 20), which is not built. Who signs off a pack's values is not specified |
| OD-61 | Report sign-off | Open, relates to OD-40 and OD-6 | Block 8 ends every report in a review stop (`SIGN_OFF_REQUIRED`); approving the run records the reviewer. The DOCX says "DRAFT: not signed off". Locking the signed copy (deck slide 77), sign-off wording (OD-40) and the LLM judge (OD-6) are not built. PDF export is not built (DOCX only) |
| OD-62 | Drawings whose text and dimensions are not DXF TEXT and DIMENSION entities | Open, relates to OD-7 | Found 2026-11-26 with a plan and a section exported as DXF from an open-source BIM tool (BIMCraft 0.12, MIT/Apache-2.0): the files pass `ezdxf` audit, but lettering is stroked outlines and hatches and dimensions are plain lines, so block 1 reads 759 and 277 lines with no dimensions, text or title block. Blocks 1 and 2 return `ok` with an empty design graph and no flag; only block 4 asks a person (`NO_TEMPLATE`). Whether blocks 1 and 2 should flag an empty result for review, and whether such drawings go through the scan (vision) path, is not decided |

## Detail items tracked in their own documents

These are "not specified in plan or deck; TBD in Phase 0" items. They live next to the text they affect, so they are not copied here. Close them in that document and note the decision there.

| Where | IDs | Topics |
|---|---|---|
| [requirements/acceptance-criteria.md](requirements/acceptance-criteria.md) §12 | TBD-AC-1 to TBD-AC-13 | Scoring of DWG/STEP/STL, meaning of a "valid" locator, curated set size, repair attempts and sandbox limits, surrogate error definition, DeepEval thresholds, pilot targets, R2 case set, R3 strain tolerance, load-test concurrency, measurement methods, deck promotion gate |
| [eval/README.md](../eval/README.md), open items | (unnumbered) | Dimension matching algorithm and `value_tol`; what counts as "labelled"; whether the internal/open rule covers the 20 STEP/STL models; ECE bin count; DWG and 3D target column; "60 to 100" reading; label export format; empty predictions; PR fast subset; "valid" locator |
| [policies/license-policy.md](policies/license-policy.md) §6 | (unnumbered) | Running the first ScanCode scan, installing Syft and ScanCode on CI, Trivy, licence checks for deck-only tools |
| [adr/](adr/README.md) | Open items section in each ADR | Per-ADR questions |

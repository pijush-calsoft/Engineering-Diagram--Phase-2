# Acceptance criteria

| | |
|---|---|
| Document | Acceptance criteria per phase and block (plan §6 Phase 0, task 1) |
| Status | **Draft, proposed targets to confirm in Phase 0.** Plan §7: "Targets in section 6 are proposals to confirm in Phase 0" |
| Sign-off | Needs director sign-off. Plan Phase 0 exit criteria: "Director signs off R1 part families and metrics (section 7)" |
| Baseline | [`engineering-diagram-platform-plan.md`](../../engineering-diagram-platform-plan.md) v0.1. The deck ([deck-text.md](../reference/deck-text.md)) is reference only; see the last sections |
| Note on OD-14 | Phase 0 task 1 says to convert "each block's In/Out line" from the director's deck. The deck in this repo has no per-block In/Out lines ([open-decisions.md](../open-decisions.md) OD-14). Inputs and outputs below are taken from plan §1, the §2.1 diagram, the §3 artifact kinds and each phase's text instead. If the In/Out lines turn up, this document must be re-checked against them |
| Last updated | 24 Nov 2026 |

## How to read this document

- Each criterion has a stable ID: `AC-P<phase>-<nn>` for phase criteria, `AC-R<n>-<nn>` for release gates. Do not reuse or renumber IDs; mark dropped ones as withdrawn.
- "Target" is the plan's number, copied exactly. Where the plan gives no number, the row says so. No target in this document is invented.
- "Measured with" comes from the plan §7 table where §7 has a matching row. Otherwise the cell cites the plan text it comes from, or says "Method not specified in plan §7; TBD in Phase 0" (TBD-AC-12).
- Plan §7: "Every pull request runs the fast subset; the full golden-set suite runs nightly and gates releases."
- Items the plan and deck leave open are listed in section 12 with `TBD-AC-n` labels. These are local labels, not OD ids. They are proposed for [open-decisions.md](../open-decisions.md) and are not yet in it. Items already logged there are cited by their OD id.

---

## 1. Phase 0: Discovery, golden data and foundations

Source: plan §6 Phase 0. Release R1 (plan §5).

### Inputs and outputs

| | Content | Source |
|---|---|---|
| Inputs | The director's deck (In/Out lines not present, OD-14); candidate drawings and models for the golden dataset; the candidate stack for the licence scan | Phase 0 tasks 1, 2, 6 |
| Outputs | Requirements and acceptance criteria, golden dataset v1 in Label Studio, contract v0.1, ADRs 001 to 008, CI pipeline, licence policy | Phase 0 deliverables |

### Criteria

| ID | Criterion | Target | Measured with | Source |
|---|---|---|---|---|
| AC-P0-01 | Director signs off R1 part families and metrics (section 7) | Sign-off recorded | Method not specified in plan §7; TBD in Phase 0 (TBD-AC-12). Related decisions: OD-1, OD-12 | Phase 0 exit criteria |
| AC-P0-02 | Golden dataset has labelled drawings | At least 60 labelled drawings | Count in Label Studio (Phase 0 deliverables) | Phase 0 exit criteria |
| AC-P0-03 | CI blocks any AGPL dependency imported in-process | Blocking (CI fails) | CI licence scan (Phase 0 task 5); first ScanCode scan (Phase 0 task 6); "CI fails on unapproved licenses" (plan §9). Plan §4.3 lists the supply-chain tools Trivy, Syft and ScanCode Toolkit | Phase 0 exit criteria; plan §9 |

Related task scope (not an exit criterion): the golden dataset is "60 to 100 drawings across DXF, DWG, vector PDF and scans, plus 20 STEP/STL models", hand-labelled for geometry, dimensions, tolerances, title block fields, material and expected parameters, using only internal or openly licensed drawings (Phase 0 task 2). Deck position differs: 50 to 100 drawings from the customer architect (deck slide 90; plan-vs-deck D10; OD-17).

---

## 2. Phase 1: Platform services and orchestrator skeleton

Source: plan §6 Phase 1. Release R1.

### Inputs and outputs per service

| Service | Inputs | Outputs | Source |
|---|---|---|---|
| Data Fabric | Uploaded files of the input types I1 to I6 (2D drawings, 3D models, requirements and prompts, material cards, load cases, FMEA sheets, solver runs, DoE, sensor signals in R3) | Versioned datasets in raw/cleaned/final zones as lakeFS branches; `fabric.file.ingested`, `fabric.dataset.versioned`, `fabric.dataset.promoted` events | §2.1 (IN to F); Phase 1 table; §3; Appendix B |
| Data Catalogue | Pipeline outputs (§2.1 PL to C); lineage records | Artifact registry, element-level lineage table, dataset lineage via OpenLineage, vector index, "cited answer" endpoint; audit trail to source drawing (O5); `catalogue.lineage.recorded` | §2.1; Phase 1 table; Appendix B |
| Model Gateway | "AI requests, token, mTLS cert" | Routed model responses, usage logs, "benchmark scores" | §4.1 (step-ca row, DeepEval row); Phase 1 table |
| Orchestrator | Chat requests | Run plans (`run.planned`), stub results for blocks 1 to 8, interrupt points for human review | §1; Phase 1 table; Appendix B |
| Console shell | `run.*` events | Chat panel, pipeline map with live block status | Phase 1 table |

Orchestrator technology differs in the deck (Java Controller, deck slides 32, 38, 62; plan-vs-deck D3; OD-9). These criteria follow the plan.

Event subjects differ in the deck. The deck uses names such as `fabric.ingested`, `run.step.done`, `audit.*` and `usage.logged` (deck slides 39, 95; plan-vs-deck I2). These criteria use the plan's Appendix B subjects.

### Criteria

| ID | Criterion | Target | Measured with | Source |
|---|---|---|---|---|
| AC-P1-01 | A file uploaded in the console produces a versioned dataset, a run with eight stub block results, lineage visible in Marquez, and an end-to-end trace in Langfuse | All four present for the uploaded file | Lineage in Marquez and trace in Langfuse, as named in the exit criterion | Phase 1 exit criteria |
| AC-P1-02 | Every gateway call is authenticated with mTLS and logged with tokens and cost | Every call | LiteLLM proxy "usage logs" (§4.1 model routing row); Langfuse "cost" (§4.1 LLM tracing row); mTLS certificates from step-ca (§4.1). Test method not specified in plan §7; TBD in Phase 0 (TBD-AC-12) | Phase 1 exit criteria |
| AC-P1-03 | Restarting any block mid-run resumes from the checkpoint | Any block | LangGraph tests (§7 Orchestrator, "recovery from failures"); Postgres checkpointer (Phase 1 Orchestrator row; §2.2) | Phase 1 exit criteria |

### Tracked metrics with no target in the plan

| Layer | What is measured | Tooling | Source |
|---|---|---|---|
| Orchestrator | Plan correctness on scripted chat scenarios, recovery from failures | LangGraph tests, Langfuse datasets | §7 |
| Gateway | Model benchmarks per task, latency, cost | DeepEval, lm-evaluation-harness | §7 |

---

## 3. Phase 2: Drawing Parser (block 1)

Source: plan §6 Phase 2. Release R1.

### Inputs and outputs

| | Content | Source |
|---|---|---|
| Inputs | 2D drawings: DXF, DWG, vector PDF, scans. 3D models: STEP, IGES, STL | §2.1 I1, I2; Phase 2 "Approach by input" |
| Outputs | `geometry` artifact: entities (line, arc, circle, spline, text, dimension), views, units, scale, locators | Phase 2 task 1; §3 artifact kind `geometry` |
| | Dimension-to-feature associations | Phase 2 task 2 |
| | Title block: part number, revision, material, scale, units, tolerances, each with per-field confidence | Phase 2 task 3 |
| | Flags, for example DWG conversion warnings; STL flagged as lossy input | Phase 2 approach table |
| | SVG render of the parsed result for the drawing workspace ("Parser" cursor layer) | Phase 2 task 6 |

### Criteria (on golden set)

| ID | Metric | Input class | Target | Measured with | Source |
|---|---|---|---|---|---|
| AC-P2-01 | Dimension value and target F1 | Vector DXF / PDF | ≥ 0.95 | pytest + custom metrics on golden set (§7 Parser) | Phase 2 exit criteria |
| AC-P2-02 | Dimension value and target F1 | Scans | ≥ 0.85 | same | Phase 2 exit criteria |
| AC-P2-03 | Title block field accuracy | Vector DXF / PDF | ≥ 0.98 | same | Phase 2 exit criteria |
| AC-P2-04 | Title block field accuracy | Scans | ≥ 0.92 | same | Phase 2 exit criteria |
| AC-P2-05 | Entities with a valid source locator | Vector DXF / PDF | 100 % | same ("locator coverage") | Phase 2 exit criteria |
| AC-P2-06 | Entities with a valid source locator | Scans | 100 % | same | Phase 2 exit criteria |
| AC-P2-07 | Calibration error (ECE) on confidences | Vector DXF / PDF | ≤ 0.05 | same ("calibration") | Phase 2 exit criteria |
| AC-P2-08 | Calibration error (ECE) on confidences | Scans | ≤ 0.08 | same | Phase 2 exit criteria |

Intent behind AC-P2-07/08: "Confidence calibration per field so that 0.6 means roughly a 60 % chance of being right" (Phase 2 task 5).

The exit table has two columns only (vector DXF / PDF and scans). How DWG (converted to DXF), STEP/IGES and STL inputs are scored is not specified in plan or deck; see section 12, TBD-AC-1.

Parser tooling differs in the deck. For PDF and OCR the deck names pypdf, Tesseract and OCRmyPDF (deck slide 62; plan-vs-deck L1). For DWG the deck names the ODA converter as a licence prerequisite (deck slides 35, 90; plan-vs-deck L3). These criteria follow the plan and do not depend on the tool.

---

## 4. Phase 3: Interpretation (block 2) and Knowledge Graph (block 3)

Source: plan §6 Phase 3. Release R1.

### Inputs and outputs

| Block | Inputs | Outputs | Source |
|---|---|---|---|
| 2 Interpretation | Parsed elements (`geometry`) from block 1; 3D topology; requirements from documents (Docling) and chat (§2.1 I3) | `design_graph` artifact: features (hole, slot, pocket, boss, fillet, rib, bend), parameters, tolerances, datums, materials, requirements, edges; typed constraints; unit and contradiction flags; low-confidence flags with a reason code, sent to block 3 | §2.1 (B1 to B2, B2 to B3); Phase 3 Interpretation tasks 1 to 5; §3 kind `design_graph` |
| 3 Knowledge Graph | Design graphs; flagged values from block 2; shape data (trimesh descriptors) | Entity relations (part, revision, mating part, material, supplier, load case, test result); similar parts with similarity and matched features; corroboration evidence with its own locators | §2.1 (B2 to B3 both ways); Phase 3 KG tasks 1 to 4 |

### Criteria

| ID | Block | Metric | Target | Measured with | Source |
|---|---|---|---|---|---|
| AC-P3-01 | 2 | Design graph matches hand-labelled graphs | ≥ 90 % of features | pytest, NetworkX graph diff (§7 "feature graph match") | Phase 3 exit criteria |
| AC-P3-02 | 3 | Low-confidence flags on the golden set correctly resolved by corroboration | At least 50 % | pytest (§7 "flag resolution precision") | Phase 3 exit criteria |
| AC-P3-03 | 3 | Flags resolved wrongly above 0.9 confidence | None | pytest (§7 "flag resolution precision") | Phase 3 exit criteria |
| AC-P3-04 | 3 | Similar-part search top-3 recall on a curated set | ≥ 0.8 | pytest (§7 "similar-part recall") | Phase 3 exit criteria |

The size and source of the "curated set" for AC-P3-04 are not specified; see TBD-AC-3.

The example constraint "minimum margin ≥ 1.5 for all load cases" (Phase 3 task 3) is an example of a parsed requirement, not an acceptance criterion.

---

## 5. Phase 4: Generation (block 4) and OpenCAD Adapters (block 5)

Source: plan §6 Phase 4. Release R1. Criteria apply "on golden set, R1 part families". R1 part families are not yet decided (OD-1, OD-12). Plan recommends prismatic machined parts and sheet-metal brackets, deferring castings and assemblies (Phase 0 task 3). The deck proposes a seat-structure domain pack instead (deck slides 10, 20, 34, 50; plan-vs-deck D7).

### Inputs and outputs

| Block | Inputs | Outputs | Source |
|---|---|---|---|
| 4 Generation | `design_graph` from block 2 | `cad_script` artifact (CadQuery or build123d), OpenSCAD output from the same design graph, parameter table with a source locator per parameter; editable model (O1) | §2.1 (B2 to B4, B4 to O1); Phase 4 Generation tasks 1 to 5; §3 kind `cad_script` |
| 5 OpenCAD Adapters | Generated solid / script from block 4; parsed drawing dimensions for the 2D diff | Validity results (`BRepCheck_Analyzer`, watertightness, self-intersection, minimum thickness); dimensional diff; exports STEP AP242, STL, glTF/GLB (O2); console thumbnails | §2.1 (B4 to B5, B5 to O2); Phase 4 OpenCAD tasks 1 to 4; §3 kind `step` |

### Criteria (on golden set, R1 part families)

| ID | Metric | Target | Where checked | Measured with | Source |
|---|---|---|---|---|---|
| AC-P4-01 | Valid solid rate | ≥ 98 % | Block 5 validity checks (OpenCAD task 1) | trimesh, OCP (§7 Generation) | Phase 4 exit criteria |
| AC-P4-02 | Features within drawing tolerance | ≥ 90 % | Block 5 dimensional verification (OpenCAD task 2) | trimesh, OCP (§7 Generation) | Phase 4 exit criteria |
| AC-P4-03 | Parameters with source locators | 100 % | Block 4 parameter table (Generation task 4) | Method not specified in plan §7; TBD in Phase 0 (TBD-AC-12). `ScriptParameter.source` supports a schema check (section 11) | Phase 4 exit criteria |
| AC-P4-04 | Share of parts generated by templates only | Tracked, no target | Block 4 (Generation task 1) | Method not specified in plan §7; TBD in Phase 0 (TBD-AC-12) | Phase 4 exit criteria |
| AC-P4-05 | Median generation time | < 60 s | Block 4 | Timings in `BlockResult.metrics` (plan §3: "timings, token usage, accuracy proxies"). Method not specified in plan §7; TBD in Phase 0 (TBD-AC-12) | Phase 4 exit criteria |

Tracked with no target in the plan: Chamfer distance or volume IoU vs reference (§7 Generation, trimesh, OCP).

---

## 6. Phase 5: Solver Connectors (block 6) and Surrogate, envelope (block 7)

Source: plan §6 Phase 5. Release R1.

### Inputs and outputs

| Block | Inputs | Outputs | Source |
|---|---|---|---|
| 6 Solver Connectors | STEP file from block 5 (work starts with reference STEP models); material cards and load cases as typed inputs (JSON, CSV); FMEA sheets parsed for failure modes | Meshes with quality checks (optional convergence study); solver results; `margins` artifact: allowable over computed stress (and displacement, buckling, fatigue where relevant) per load case, with the governing location as a locator | §2.1 (I4, B5 to B6); Phase 5 Solver tasks 1 to 4; §3 kind `margins` |
| 7 Surrogate, envelope | Margins from block 6; DoE designs (§2.1 I5); requirement threshold | DoE batches, sensitivity analysis (SALib), surrogates registered in MLflow with training data versions, failure envelope with an uncertainty band, solver spot-checks near the boundary; margin report and failure envelope (O3) | §2.1 (B6 to B7, B7 to O3); Phase 5 Surrogate tasks 1 to 4 |

Surrogate method differs in the deck (PINN and reduced-order models, deck slides 50, 65; plan-vs-deck D9; OD-16). AC-P5-02 does not depend on the method.

### Criteria

| ID | Block | Metric | Target | Measured with | Source |
|---|---|---|---|---|---|
| AC-P5-01 | 6 | Benchmark problems (NAFEMS-style cases and hand calculations) vs reference | Within 3 % of reference | Reference cases (§7 Solvers "benchmark error") | Phase 5 exit criteria; Solver task 6 |
| AC-P5-02 | 7 | Surrogate error on held-out DoE points | ≤ 5 % | scikit-learn, MLflow (§7 Surrogate "hold-out error") | Phase 5 exit criteria |
| AC-P5-03 | 7 | Prediction intervals | Calibrated 90 % intervals | scikit-learn, MLflow (§7 Surrogate "interval calibration") | Phase 5 exit criteria |
| AC-P5-04 | 6 | Every margin links to the solver run, load case row and model version | Every margin | Method not specified in plan §7; TBD in Phase 0 (TBD-AC-12). Required `Margin` fields support a schema check (section 11) | Phase 5 exit criteria |

Tracked with no target in the plan: mesh convergence (§7 Solvers).

Plan risk 3 (§10) states the benchmark gate is per connector: "Benchmark gate per connector". The error definition for AC-P5-02 and the calibration test for AC-P5-03 are not specified; see TBD-AC-5.

Solver choice differs in the deck: CalculiX via FreeCAD FEM and Ansys result import (deck slides 20, 24, 65, 90; plan-vs-deck L4; OD-3, OD-27). AC-P5-01 follows the plan and is scored per connector (§10 risk 3). Whether it applies to an Ansys result import is open (OD-3, OD-27).

---

## 7. Phase 6: Insight report (block 8), audit trail and R1 hardening

Source: plan §6 Phase 6. Release R1.

### Inputs and outputs

| Part | Inputs | Outputs | Source |
|---|---|---|---|
| 8 Insight, report | Numbers from the Run Store, inserted by code (Insight task 2); content for the sections summary, inputs, model, margins, envelope, flags, assumptions (Insight task 1); LLM narrative through the Model Gateway (Insight task 2) | `report` artifact: PDF or DOCX with sections summary, inputs, model, margins, envelope, flags, assumptions (O4) | §2.1 (B7 to B8, B8 to O4, G to B8); Phase 6 Insight tasks 1 to 3 |
| Audit trail | Lineage held by the Data Catalogue | Element-level lineage export (JSONL plus OpenLineage events): output item, source locators, block, version, model used, prompt version, reviewer; console highlight of the source on the drawing (O5) | §2.1 (C to O5); Phase 6 Audit tasks 1, 2 |

### Criteria

The plan has no separately headed "Exit criteria" list for Phase 6; the R1 gate requires "All Phase 2 to 6 exit criteria". The rows below come from the Phase 6 task text and §7. Treating them as the Phase 6 exit criteria is a proposal to confirm in Phase 0 (TBD-AC-7).

| ID | Metric or check | Target | Measured with | Source |
|---|---|---|---|---|
| AC-P6-01 | Numeric claim verification rate | 100 % ("must be 100 %") | Deterministic checker (§7 Reports) | §7; Phase 6 Insight task 3 |
| AC-P6-02 | Every number in a report is inserted from the Run Store by code, never typed by the model | Every number | Method not specified in plan §7; TBD in Phase 0 (TBD-AC-12). Plan §7 measures "numeric claim verification rate"; Insight task 3 checks that every numeric claim and citation resolves to the Run Store | Phase 6 Insight task 2 |
| AC-P6-03 | Any fact-check failure blocks the report | Blocking | Deterministic checker, DeepEval (§7 Reports; Insight task 3) | Phase 6 Insight task 3; §10 risk 4 |
| AC-P6-04 | Faithfulness and hallucination of the narrative | Measured; no threshold in plan (TBD-AC-6) | DeepEval (§7 Reports) | §7; Phase 6 Insight task 3 |
| AC-P6-05 | Lineage export carries output item, source locators, block, version, model used, prompt version, reviewer | Every output item | Method not specified in plan §7; TBD in Phase 0 (TBD-AC-12) | Phase 6 Audit task 1 |
| AC-P6-06 | Selecting any item in the console highlights its source on the drawing | Any item | Method not specified in plan §7; TBD in Phase 0 (TBD-AC-12). Plan §4.3 lists Playwright as a testing tool | Phase 6 Audit task 2 |
| AC-P6-07 | Console completion: chat with run plans, live pipeline map, drawing workspace with per-agent layers, 3D viewer, script editor, margins and envelope, files, audit trail, review queue for flags | All listed views present | Method not specified in plan §7; TBD in Phase 0 (TBD-AC-12) | Phase 6 "Console completion" |
| AC-P6-08 | Hardening done: load test (concurrent runs), chaos test (kill blocks mid-run), security review (prompt injection through drawing text, sandbox escape in generated code, tenant isolation), backup and restore drill, runbooks | Each performed and recorded; no numeric target in plan (TBD-AC-11) | The listed tests themselves (Phase 6 "Hardening"); how results are recorded is TBD in Phase 0 (TBD-AC-12) | Phase 6 "Hardening" |

---

## 8. Release gate R1

Source: plan §6 Phase 6 "R1 release gate". Planned date 24 May 2027 (plan §5). Deck position: "Release 1 in 8 weeks" (deck slides 1, 13, 14, 82; plan-vs-deck D1; OD-8).

| ID | Criterion | Target | Source |
|---|---|---|---|
| AC-R1-01 | All Phase 2 to 6 exit criteria met on the golden set | AC-P2-xx to AC-P6-xx all met | R1 release gate |
| AC-R1-02 | Pilot with two or three internal engineers on real (non-client or properly scoped) drawings; task completion and time saved recorded | Pilot done and recorded; no target for task completion or time saved in plan (TBD-AC-8) | R1 release gate |
| AC-R1-03 | Zero unresolved AGPL findings | 0 | R1 release gate |
| AC-R1-04 | SBOM published | Published | R1 release gate; CI SBOM step (Phase 0 task 5). Plan §4.3 lists the supply-chain tools Trivy, Syft and ScanCode Toolkit; it does not name one tool for the SBOM |
| AC-R1-05 | Director sign-off | Recorded | R1 release gate |

---

## 9. Phase 7: Optimiser, redlines and write-back (R2) and release gate R2

Source: plan §6 Phase 7. Planned R2 gate 5 Jul 2027 (plan §5). Deck timing differs (deck slide 81; plan-vs-deck D2).

### Inputs and outputs

| | Content | Source |
|---|---|---|
| Inputs | Objectives and constraints from requirements; surrogate from block 7; mating interfaces from Knowledge Graph relations; real solver for confirmation; Model Gateway for explanations | §2.1 (B7 to OPT, G to OPT); Phase 7 tasks 1 to 3 |
| Outputs | Ranked changes with explanations (margin gain, mass change, manufacturability notes, binding constraints); new DXF revision with a REDLINE layer (revision clouds, change notes, revision triangle) plus a marked-up PDF; updated script and parameter table with changed rows highlighted; draft write-back through an approval workflow (O6) | §2.1 (OPT to O6); Phase 7 tasks 3 to 5 |

### Criteria (R2 exit criteria)

| ID | Criterion | Target | Measured with | Source |
|---|---|---|---|---|
| AC-R2-01 | Top-ranked change meets all constraints after solver confirmation | ≥ 90 % of cases | Solver confirmation of the top-ranked change; case set not specified in plan or deck (TBD-AC-9) | R2 exit criteria |
| AC-R2-02 | Every redline item links to its change rationale and runs | Every item | Method not specified in plan §7; TBD in Phase 0 (TBD-AC-12) | R2 exit criteria |
| AC-R2-03 | No write-back possible without a recorded approval | No exceptions | Method not specified in plan §7; TBD in Phase 0 (TBD-AC-12). Related events: `review.*` (Appendix B) | R2 exit criteria; principle 5 |

Tracked with no target in the plan: comparison against a baseline engineer-chosen change on golden cases (Phase 7 task 6). This is a separate evaluation from AC-R2-01.

The deck uses `review.requested` but also `design.ranked` and other subjects not in the plan (deck slides 39, 95; plan-vs-deck I2). AC-R2-03 follows the plan's `review.*` subjects.

---

## 10. Phase 8: Digital twin (R3) and release gate R3

Source: plan §6 Phase 8. Planned R3 gate 30 Aug 2027 (plan §5). Deck timing differs (deck slide 81; plan-vs-deck D2).

### Inputs and outputs

| | Content | Source |
|---|---|---|
| Inputs | Test-rig and sensor signals over MQTT (Mosquitto) and OPC UA (asyncua), into NATS and the Data Fabric; surrogate; model locations; S-N curves from the material card | §2.1 I6; Phase 8 tasks 1, 3, 5 |
| Outputs | Cleaned signals and features (resampling, filtering, rainflow counts, peak and RMS); twin state; calibrated parameters (PyMC); remaining life with uncertainty; alerts through Prometheus Alertmanager; draft redlines or report addenda through the Phase 7 approval workflow (O6); `twin.state.updated`, `twin.alert.raised` | §2.1 (TW to O6); Phase 8 tasks 2 to 7; Appendix B |

### Criteria (R3 exit criteria)

| ID | Criterion | Target | Measured with | Source |
|---|---|---|---|---|
| AC-R3-01 | On rig data, predicted strain within agreed tolerance of measured | "Agreed tolerance"; value not specified (TBD-AC-10) | Comparison on rig data, as named in the exit criterion | R3 exit criteria |
| AC-R3-02 | Remaining-life estimates reproducible from stored data | Reproducible | Re-run from stored data, as named in the exit criterion | R3 exit criteria |
| AC-R3-03 | Alerts tested end to end | Tested | End-to-end alert test, as named in the exit criterion; alerts through Prometheus Alertmanager (Phase 8 task 6) | R3 exit criteria |
| AC-R3-04 | Every twin-driven change goes through approval | Every change | Phase 7 approval workflow (Phase 8 task 7). Test method not specified in plan §7; TBD in Phase 0 (TBD-AC-12) | R3 exit criteria; principle 5 |

The deck names the twin alert subject `twin.alert` (deck slides 39, 95; plan-vs-deck I2). These criteria follow the plan's `twin.state.updated` and `twin.alert.raised` (Appendix B).

---

## 11. Traceability: which contract schema supports which criterion

Read from `contracts/src/edp_contracts/` (contract v0.1, artifact schemas v0.1). "Enforces" means a payload that breaks the rule fails pydantic validation. "Does not enforce" lists what still needs a runtime or evaluation check.

| Criterion | Schema element | Enforces | Does not enforce |
|---|---|---|---|
| AC-P2-05, AC-P2-06 (entities with a valid source locator 100 %) | `artifacts/geometry.py`: `GeometryEntity.locator: SourceLocator` is required | Every entity has a locator with `file_id`, `version` and `confidence` | That the locator is valid; the meaning of "valid" is not specified (TBD-AC-2) |
| AC-P2-07, AC-P2-08 (ECE) | `block.py`: `SourceLocator.confidence = Field(ge=0, le=1)`, required. `TitleBlockField.locator` required ("confidence lives on the locator") | Every entity, and every title block field that is present, has a confidence in [0, 1] | Calibration itself. `Geometry.title_block` and each `TitleBlock` field are optional, so a missing field carries no confidence |
| AC-P2-03, AC-P2-04 (title block accuracy) | `TitleBlock` fields `part_number`, `revision`, `material`, `scale`, `units`, `tolerances` (Phase 2 task 3) | The field set to score | Field values; all fields are optional |
| AC-P2-01, AC-P2-02 (dimension F1) | `EntityKind` includes `"dimension"`; values sit in `GeometryEntity.data: dict` | Dimension entities can be represented | Dimension value and target structure: `data` is untyped ("typed per kind in a later version") |
| AC-P3-01 (feature match) | `artifacts/design_graph.py`: `FeatureType` literal (hole, slot, pocket, boss, fillet, rib, bend); `DesignNode` requires `feature_type` exactly when `kind == "feature"`; `DesignGraph` requires unique node ids and edges that reference existing nodes | A well-formed graph for NetworkX diff | Locators on nodes: `DesignNode.sources` defaults to an empty list. Edge relation names are free text |
| AC-P3-02, AC-P3-03 (flag resolution) | `block.py`: `Flag.code` required (reason code, e.g. `LOW_CONFIDENCE`); `severity` defaults to `"review"`; optional `target` locator | Each flag has a reason code | Resolution outcome and its confidence: no field on `Flag`. A flag may omit `severity` and `target` |
| AC-P4-03 (parameters with source locators 100 %) | `artifacts/cad_script.py`: `ScriptParameter.source: SourceLocator` is required | Every parameter has a source locator | The per-parameter comment (Phase 4 task 4): `ScriptParameter.comment` is optional |
| AC-P4-05 (median generation time) | `BlockResult.metrics: dict` ("timings, token usage, accuracy proxies") | A place to record timings | Any timing field or unit |
| AC-P5-04 (margin links) | `artifacts/margins.py`: `Margin.solver_run_id: str`, `Margin.load_case_row: SourceLocator`, `Margin.model_version: str`, all required; `Margin.governing_location: SourceLocator` required (Solver task 4) | Every margin carries the three links and a governing location | That the run, row and version exist in the Run Store |
| AC-P5-02, AC-P5-03 | None. No surrogate, DoE or envelope schema exists (Phase 0 task 4 names only `geometry`, `design_graph`, `cad_script`, `margins`, `report`) | | |
| AC-P6-01 to AC-P6-03 (fact-check) | `artifacts/report.py`: `NumericClaim.run_store_ref` required; `ReportSection.claim_ids`; `Report.unresolved_claim_ids()` returns claim ids cited by a section but missing from `claims`. `SectionKey` matches the seven template sections (Insight task 1); `ReportFormat` is `pdf` or `docx` | Every claim has a Run Store pointer | Unresolved citations: `unresolved_claim_ids()` is a plain method, not a validator, so a report that cites unknown claim ids still validates. It supports a runtime check only when the checker calls it. Also not enforced: that `run_store_ref` resolves and the value matches the Run Store; numbers typed into section `text` without a claim id. Insight task 3 has the deterministic checker confirm that "every numeric claim and citation resolves to the Run Store"; that covers resolution. Whether it also checks that the value matches is not specified in plan §7 or Phase 6; TBD in Phase 0 (TBD-AC-12). Detecting numbers typed into narrative text is a proposed checker scope, not plan text (AC-P6-02; TBD-AC-12) |
| AC-P6-05 (lineage export) | `SourceLocator`; event subject `catalogue.lineage.recorded` in `events.py` | Locator shape | The export record (block, version, model used, prompt version, reviewer): no schema yet |
| AC-R2-03, AC-R3-04 (approval before write-back) | Event subjects `review.requested`, `review.resolved` in `events.py` (Appendix B payload: flag or write-back id, reviewer, decision) | Subject names only | Approval itself; no redline, write-back or approval schema yet |
| AC-R3-01 to AC-R3-03 | Event subjects `twin.state.updated`, `twin.alert.raised` | Subject names only | No twin schema yet |

Schema gaps above are notes for the contract owner. This document does not change `contracts/`.

---

## 12. Proposed open items found while writing this document

Each item below is "Not specified in plan or deck; TBD in Phase 0". The `TBD-AC-n` labels are local to this document and are not OD ids. They are proposed for [open-decisions.md](../open-decisions.md), to be added by its owner.

The golden set vs customer drawing set question is not listed here. Plan and deck both address it and differ; it is already logged as OD-17 (plan-vs-deck D10). It affects every golden-set criterion.

| ID | Item | Affects |
|---|---|---|
| TBD-AC-1 | How DWG (via DXF), STEP/IGES and STL inputs are scored; the Phase 2 table has columns for vector DXF / PDF and scans only | AC-P2-01 to AC-P2-08 |
| TBD-AC-2 | What makes a source locator "valid" (for example, resolves to a Data Fabric file id and version) | AC-P2-05, AC-P2-06 |
| TBD-AC-3 | Size and source of the "curated set" for similar-part recall | AC-P3-04 |
| TBD-AC-4 | Maximum repair attempts "N" and sandbox CPU and time limits for generated code | Phase 4 Generation task 3 |
| TBD-AC-5 | Surrogate error definition (relative or absolute, mean or max) and the test for "calibrated 90 % intervals"; list of benchmark cases | AC-P5-01 to AC-P5-03 |
| TBD-AC-6 | Thresholds for DeepEval faithfulness and hallucination | AC-P6-04 |
| TBD-AC-7 | Whether the Phase 6 rows in section 7 are the "Phase 6 exit criteria" the R1 gate refers to | AC-R1-01 |
| TBD-AC-8 | Targets for pilot task completion and time saved | AC-R1-02 |
| TBD-AC-9 | Number and source of "cases" for the R2 optimiser criterion | AC-R2-01 |
| TBD-AC-10 | Value of the "agreed tolerance" for predicted vs measured strain | AC-R3-01 |
| TBD-AC-11 | Concurrency level for the Phase 6 load test | AC-P6-08 |
| TBD-AC-12 | Measurement method for criteria with no matching plan §7 row | AC-P0-01, AC-P1-02, AC-P4-03 to AC-P4-05, AC-P5-04, AC-P6-02, AC-P6-05 to AC-P6-08, AC-R2-02, AC-R2-03, AC-R3-04 |
| TBD-AC-13 | How the deck's model promotion gate (deck slide 28) relates to AC-P4-01. Whether the gate is in R1 scope is already logged as OD-13 (plan-vs-deck D8) | Section 13; AC-P4-01 |

---

## 13. Deck references (not baseline)

These come from the deck and are **reference only**. They are not plan criteria and carry no AC IDs. Use them as input when the targets are confirmed in Phase 0.

### Pilot success measures (deck slide 91, "proposed")

The deck gives no numeric targets here: "Targets are set with the customer in the pilot."

| Measure | Deck definition | Nearest plan criterion |
|---|---|---|
| Interpretation accuracy | Share of dimensions read correctly on a customer drawing set, before review | AC-P2-01, AC-P2-02 (plan uses the golden set; D10) |
| Model fidelity | Share of generated models that pass the validity check and match the drawing within tolerance | AC-P4-01, AC-P4-02 |
| Surrogate error | Gap to the solver on held-out cases, against the 5 % gate | AC-P5-02 |
| Time to first margin report | Hours from drawing to margin report, against the current process | AC-R1-02 (time saved recorded) |
| Engineer acceptance | Share of generated models and reports approved after review with no figure corrected, and review time per item | None in plan |

### Model promotion gate (deck slide 28, "proposed starting values")

| Check | Pass rule |
|---|---|
| Geometry validity | A valid solid on 95 % or more of test prompts |
| Task quality | Beats the base model on fidelity by 5 points or more |
| Speed | p95 latency within 20 % of the base model |
| Resources | Fits the GPU slice assigned to the model |

This gate applies to promoting a fine-tuned model. The deck places it in R1: "benchmark harness (F-22), fine-tuning pipeline (F-23) and secure access (F-14) in Release 1" (deck slide 28). Deck slide 14 says "F-17 and F-23 move to Release 2", so the deck is not consistent on this. The plan has no fine-tuning or promotion gate in R1 (plan-vs-deck D8; OD-13). Plan AC-P4-01 (valid solid rate ≥ 98 % on golden-set parts) is the nearest plan criterion. Whether the gate is in R1 scope is open under OD-13 (D8). How it relates to AC-P4-01 is open (TBD-AC-13). They are not merged here.

### Non-functional targets (deck slide 96, "proposed starting targets")

The deck says: "All targets are proposals for the pilot, not commitments." Sprint and demo references follow the deck timeline (D1). "Controller" is the deck's Java Controller (D3, OD-9).

| Area | Deck proposed target | Deck check |
|---|---|---|
| Controller API | p95 under 300 ms for non-AI calls | Load test in Sprint 4; Prometheus histograms |
| Model calls | First token under 2 s on the pilot GPU for the default model; 1, 4 and 16 parallel requests benchmarked | Model Gateway usage log; Sprint 2 GPU benchmark |
| Drawing Parser | Size, page, time and memory limits set from Phase 0 measurements; one crash never stops other jobs | Measuring script in the repo; fault-injection tests |
| Pilot scale | 20 concurrent users, one workspace per customer project | Scale test in Sprint 4 |
| Availability | 99.5 % in pilot working hours; jobs survive a restart | Health checks; restart-mid-job test |
| Security | mTLS and short-lived tokens; TLS in transit, encryption at rest; no content in logs | Security review in Sprint 4; log scan in CI |
| Interpretation and simulation | Dimension read accuracy measured on a customer drawing set. Surrogate error within 5 % of the solver on held-out cases. Every margin shows its uncertainty | Held-out test set; Sprint 4 benchmark report |
| Insight reports | Every figure matches the Run Store. A 10-page report in under 60 s. The narrative never adds a number | Fact-check test set; Sprint 4 benchmark |
| Retention and audit | Drawing and result retention is a setting (default proposed in Parser Phase 0); audit log kept for the pilot | Cleanup task; audit export |

The deck also has a requirements traceability matrix (deck slide 97), mapping requirements to deck slides and releases. It is not reproduced here.

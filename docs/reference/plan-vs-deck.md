# Plan vs deck: differences to resolve

| | |
|---|---|
| Plan | [`engineering-diagram-platform-plan.md`](../../engineering-diagram-platform-plan.md), v0.1, 24 Nov 2026 |
| Deck | `AI_Engineering_Diagram_Platform_2170_0615 (1).pptx`, 98 slides; text copy in [deck-text.md](deck-text.md) |
| Rule used in this repo | **The plan is the working baseline.** The deck is reference material. Nothing below is decided here; each row is listed in [open-decisions.md](../open-decisions.md) until the accountable owner decides |
| Last checked | 24 Nov 2026 (both sources read in full) |

## 1. Differences that change architecture or scope

| # | Topic | Plan says | Deck says | Effect on this repo |
|---|---|---|---|---|
| D1 | R1 duration | Phases 0 to 6, assumed start 7 Dec 2026, R1 gate 24 May 2027 (§5) | "Release 1 in 8 weeks", four two-week sprints, 32 features, 290 story points (slides 1, 13, 14, 82) | Phase tracker follows the plan's phases |
| D2 | R2 and R3 timing | R2 gate 5 Jul 2027, R3 gate 30 Aug 2027 (§5) | Three releases over 24 weeks: R2 weeks 9 to 16, R3 weeks 17 to 20 (slide 81) | None yet |
| D3 | Controller / orchestrator | LangGraph planner graph (Python) with Postgres checkpointer; Temporal for long jobs (§2.2, Phase 1) | Controller in **Java** ("Confirmed: Java. Spring Boot proposed"), stateless, with JPA, Kafka and Valkey (slides 32, 38, 62) | `orchestrator/` follows the plan; no Java module is created until decided |
| D4 | View / console | React + Vite + TypeScript (§4.3) | "Node.js, React, three.js viewer" ("Confirmed: Node.js") (slide 62) | Compatible if Node.js means the build and runtime for React; to confirm |
| D5 | Event bus | NATS JetStream primary, Kafka alternative (§2.2, §4.1) | "Kafka confirmed"; Apache Pulsar as an option (slides 62, 64) | Event subject names only in `edp_contracts.events`; no broker client yet |
| D6 | Model hosting | Self-hosted vLLM behind LiteLLM proxy; §11 Q5 asks whether hosted model APIs are allowed | "Confirmed: in-house and AWS Bedrock" (slide 62); Bedrock as an alternative per project (slide 88) | None yet |
| D7 | R1 domain / part families | Recommends prismatic machined parts and sheet-metal brackets; defer castings and assemblies (Phase 0 task 3) | Seat structure domain pack: seat frame and recliner bracket, FMVSS and ECE load cases (slides 10, 20, 34, 50) | Golden-set manifest schema is family-agnostic |
| D8 | Release contents | R1 drawing to model, margins, report; R2 optimiser and redlines; R3 twin (§1) | R1 also has Variant Comparison (F-18), benchmark harness (F-22), physics-informed surrogate; R2 adds assemblies, FMEA and DVP links, voice, prompt-triggered runs, adapter onboarding AD-1; R3 adds chaos models, native CAD write-back, 3D from views, exhaust and body packs (slides 10, 11, 14, 81, 87) | None yet |
| D9 | Surrogate method | DoE + Gaussian processes (scikit-learn, GPyTorch, SMT), MLflow (Phase 5, §4.2) | PINN and reduced-order models (DeepXDE or NVIDIA Modulus), ONNX Runtime or OpenVINO for CPU inference (slides 50, 65) | None yet |
| D10 | Golden data source | 60 to 100 internal or openly licensed drawings plus 20 STEP/STL; client drawings only inside that client's scope (Phase 0 task 2, principle 7) | 50 to 100 drawings from the customer architect, needed by week 1; 300 to 500 solver runs for the seat frame (slide 90) | Golden-set data never stored in git (`.gitignore`) |

## 2. Differences in interfaces

| # | Topic | Plan says | Deck says |
|---|---|---|---|
| I1 | Plug-in endpoints | `POST /run`, `GET /health`, `GET /contract`, plus an MCP tool with the same signature (§3) | Manifest (name, version, capabilities), endpoints `/health`, `/run`, `/status`, `/result`, events, permissions, versioned schemas, lifecycle register/enable/run/disable (slide 38) |
| I2 | Event subjects | `fabric.file.ingested`, `fabric.dataset.versioned`, `fabric.dataset.promoted`, `run.planned`, `run.block.*`, `catalogue.lineage.recorded`, `review.*`, `twin.*` (Appendix B) | `fabric.ingested`, `.parsed`, `.cleaned`, `.validated`, `.promoted`, `catalogue.ready`, `run.step.done`, `review.requested`, `audit.*`, `usage.logged`, `interpretation.done`, `model.generated`, `simulation.done`, `envelope.ready`, `insights.ready`, `report.generated`, `report.signed`, `design.ranked`, `twin.alert` (slides 39, 95) |
| I3 | API paths | Unversioned (`/run`) | Versioned `/v1/...` per service, e.g. `POST /v1/parse-jobs` (slides 43, 95) |
| I4 | Adapter contract | Block protocol (§3) | Separate `CadAdapter` protocol: `detect`, `scaffold`, `generate`, `validate_cmd`, `export_cmd` (slide 47) |

`contracts/` implements the plan's column (I1, I2). The deck's `/status`, `/result` and versioned paths are not added until decided.

## 3. Differences in libraries

| # | Area | Plan | Deck |
|---|---|---|---|
| L1 | PDF and OCR | pdfplumber / pypdfium2; PaddleOCR / docTR (§4.2 block 1) | ezdxf, pypdf, pdfplumber, OpenCV, Tesseract, OCRmyPDF (slide 62) |
| L2 | Data Fabric | SeaweedFS + lakeFS zones as branches (§4.1, Phase 1) | Python workers; Airflow or Dagster scheduler; bronze/silver/gold paths (slides 39, 62) |
| L3 | DWG | LibreDWG `dwg2dxf` primary; ODA File Converter fallback after legal review (§4.2, §9) | "ODA converter for DWG" as a licence prerequisite (slides 35, 90) |
| L4 | Solvers | CalculiX, Code_Aster, FEniCSx; Gmsh / Netgen (§4.2 block 6) | CalculiX via FreeCAD FEM; Ansys result import (slides 20, 24, 65, 90) |
| L5 | Identity / roles | Keycloak OIDC (§4.1) | Roles Admin, Design lead, Design engineer, Analyst, Reviewer, Viewer from a JSON file in R1 (slide 64) |
| L6 | Dashboards | Grafana optional, AGPL, unmodified separate service (§4.2, §9) | Prometheus, Grafana (slides 62, 96) |

Every library in either column still goes through the Phase 0 licence check (plan §4 preamble, §9).

## 4. In the deck only, useful as reference

- Non-functional targets: Controller p95 under 300 ms, first token under 2 s, 20 concurrent users, 99.5 % availability in pilot hours (slide 96). Labelled "proposals for the pilot, not commitments".
- Parse-job design: idempotent on file hash plus parser version, bounded queue with 429 and Retry-After, one subprocess per job, result saved before the job record (slide 43).
- Insight and Report Engine stages: Run Store, Insight Builder, Narrative Writer, Report Assembler, Review and Export (slide 40).
- Model promotion gate starting values: valid solid on at least 95 % of test prompts, beats base on fidelity by 5 points or more, p95 latency within 20 % of base (slide 28).
- Requirements traceability matrix (slide 97).

## 5. Plan text that this repo could not act on

- Phase 0 task 1 says to convert "each block's In/Out line" from "the director's deck" into acceptance criteria. The deck in this repository has no per-block In/Out lines. Either the director's deck is a different file, or the criteria come from elsewhere. Logged as decision OD-14.

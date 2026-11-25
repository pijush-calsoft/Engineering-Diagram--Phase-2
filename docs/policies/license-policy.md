# Licence policy

| | |
|---|---|
| Source | Plan §9 "License policy and watch-list"; GPL and AGPL notes from plan §4.1 and §4.2 |
| Plan task | Phase 0 task 6: "Write the license policy (section 9) and run the first ScanCode scan on the candidate stack" (plan §6, Phase 0) |
| Exit criterion served | "CI blocks any AGPL dependency imported in-process" (plan §6, Phase 0 exit criteria) |
| Enforced by | [`scripts/ci/license_policy.toml`](../../scripts/ci/license_policy.toml), [`scripts/ci/src/edp_ci/license_gate.py`](../../scripts/ci/src/edp_ci/license_gate.py), [`scripts/ci/run_ci.sh`](../../scripts/ci/run_ci.sh) |
| Status | Draft. Needs review by the accountable owner, and by legal where the plan flags it |
| Last updated | 25 Nov 2026 |

**Licences in this document are taken from the plan.** The plan says: "Licenses are listed as understood at the time of writing; confirm each one in Phase 0 with the license scan and, where flagged, with legal" (plan §4 preamble). Nothing here has been confirmed by a scan or by legal yet.

## 1. Policy

Plan §9, in full:

> Permissive licenses (MIT, BSD, Apache 2.0, PostgreSQL, MPL 2.0) are allowed anywhere. LGPL is allowed when used as a library without modification. GPL tools run as separate processes or containers, especially if the platform may be shipped on-premises to clients (GPL obligations trigger on distribution). AGPL components are not imported into our services; if used at all, they run unmodified as separate network services after legal review. CI fails on unapproved licenses.

| Licence class | Rule (plan §9) | Gate category |
|---|---|---|
| Permissive: MIT, BSD, Apache 2.0, PostgreSQL, MPL 2.0 | Allowed anywhere | `allowed` |
| LGPL | Allowed when used as a library without modification | `conditional`: warning, passes |
| GPL | Runs as separate processes or containers | `denied_in_process`. This includes `GPL-1.0-only` and `GPL-1.0-or-later`: GPL per the §9 policy text |
| AGPL | Never imported into our services. If used at all, runs unmodified as a separate network service after legal review | `denied_in_process` |
| SSPL, RSAL, BUSL (BSL) | Plan §9 policy text does not name them. The watch-list replaces every component under them (Redis 8+ "AGPL / SSPL / RSAL", HashiCorp Vault and Terraform "BSL") | `denied_in_process`. The ids `SSPL`, `SSPL-1.0`, `BUSL`, `BUSL-1.0`, `BUSL-1.1` and `RSAL` are derived from the §9 watch-list, not from the §9 policy text. The plan gives no version for any of them; `BUSL-1.0` and `BUSL-1.1` are versions of the BSL named in the watch-list. Confirm in Phase 0 |
| Anything else | "CI fails on unapproved licenses" | `unknown`: fails |

Plan §11 Q2 (OD-2): whether the platform is hosted by Calsoft, deployed into client environments, or both "changes how strictly GPL components must be isolated". Until OD-2 is decided, the gate applies the strict reading.

### Additions not named in plan §9

| Id | Why it is in `allowed` | Status |
|---|---|---|
| `PSF-2.0` | `typing_extensions` declares `License-Expression: PSF-2.0`, and pydantic depends on it | Not named in plan §9. Proposed. Needs confirmation by the accountable owner and legal. Accepted only through the id `PSF-2.0`. The unversioned classifier "Python Software Foundation License" is not mapped and fails as `unknown` |
| `ISC` | Common permissive licence; no installed distribution uses it at the time of writing | Not named in plan §9. Proposed. Needs confirmation by the accountable owner and legal |
| `BSD` (no clause count) | Plan §9 says "BSD" without a variant. Some metadata says only "BSD License" (for example `colorama`) | Confirm in Phase 0 |

## 2. Watch-list (plan §9)

| Component | Issue | Decision |
|---|---|---|
| MinIO Community | No longer maintained; AGPL | Use SeaweedFS or Ceph RGW |
| Redis 8+ | AGPL / SSPL / RSAL | Use Valkey |
| PyMuPDF | AGPL or commercial | Use pdfplumber / pypdfium2 |
| Ultralytics YOLO | AGPL or commercial | Use RT-DETR, D-FINE, MMDetection or Detectron2 |
| HashiCorp Vault, Terraform | BSL | Use OpenBao, OpenTofu |
| LibreDWG | GPLv3 | Isolated CLI container |
| OpenSCAD, Gmsh, CalculiX, Code_Aster | GPL | Separate processes or containers |
| Neo4j Community | GPLv3, single node | Separate service, or Apache AGE instead |
| Grafana | AGPL | Optional, unmodified, separate service |
| ODA File Converter | Free but proprietary EULA | Fallback only, after legal review |
| Qwen, Llama and other model weights | Licenses vary by family and size | Check per model before deployment |
| CAD research datasets (DeepCAD, ABC, Fusion 360 Gallery and derivatives) | Some are research-only or have platform terms | Use for research baselines only unless the license allows commercial use |
| LangSmith | Commercial SaaS | Optional; Langfuse is the open-source default |

## 3. Isolation notes from plan §4

These are the licence notes the plan gives per component. Licences are as stated in the plan.

| Component | Where | Licence (plan) | What the plan says to do |
|---|---|---|---|
| LibreDWG `dwg2dxf` | Block 1, Drawing Parser (§4.2) | GPLv3 | Run as an isolated CLI. Phase 2: "LibreDWG `dwg2dxf` in an isolated container, then the DXF path" (plan §6, Phase 2) |
| ODA File Converter | Block 1 (§4.2) | Free but proprietary | Use only if LibreDWG fails on a client's DWG versions |
| PyMuPDF, Ultralytics YOLO | Block 1 (§4.2) | AGPL | Avoid |
| Qwen2.5-VL / Qwen3-VL | Block 1 (§4.2) | "Qwen licenses differ by model size" | Check per model (watch-list) |
| Qwen2.5-Coder / Qwen3-Coder via vLLM | Block 4 (§4.2) | Not stated in the Block 4 row | Plan §9 watch-list "Qwen, Llama and other model weights": "Check per model before deployment" |
| Neo4j Community | Block 3, Knowledge Graph (§4.2) | GPLv3, single-node | Apache AGE keeps the graph inside Postgres |
| OpenSCAD | Block 4, Generation (§4.2) | GPL-2 | CLI only |
| CAD-Coder, Text-to-CadQuery, CAD-Recode, CAD datasets | Block 4 (§4.2) | Not stated | "Check each research model and dataset license; several CAD datasets are research-only" |
| OCCT (via OCP), FreeCAD | Block 5, OpenCAD Adapters (§4.2) | OCCT: LGPL 2.1 with exception; FreeCAD: LGPL | LGPL rule: unmodified library |
| Gmsh, CalculiX, Code_Aster | Block 6, Solver Connectors (§4.2) | GPL | Run as separate processes or containers |
| docxtpl | Block 8, Insight and report (§4.2) | LGPL 2.1 | LGPL rule: unmodified library |
| asyncua | Digital twin, R3 (§4.2) | LGPL | LGPL rule: unmodified library |
| Eclipse Ditto | Digital twin, R3 (§4.2) | EPL 2.0 | Not covered by the §9 policy classes. Open item (section 6) |
| Grafana | Digital twin dashboards, if used (§4.2) | AGPL | "should stay an unmodified separate service" |
| Ceph RGW | Object storage alternative (§4.1) | LGPL | Alternative to SeaweedFS |
| HashiCorp Vault | Secrets (§4.1) | BSL | Not used; OpenBao (MPL 2.0) instead |
| Redis 8+ | Cache, queues (§4.1) | AGPL/SSPL/RSAL tri-licensed | Not used; Valkey (BSD-3) instead |

Guiding principle 6 (plan §2.3): "GPL and AGPL tools run as isolated services or CLIs, and every dependency is scanned in CI." Risk 6 "License contamination" is mitigated by "Policy in section 9, CI scan, isolated GPL services" (plan §10).

### Deck positions on the same topic

The plan is the baseline (see [plan-vs-deck.md](../reference/plan-vs-deck.md)).

| Topic | Deck | Plan | Ref |
|---|---|---|---|
| GPL isolation | "GPL tools (OpenSCAD, CalculiX, Gmsh) run as separate processes, not linked; FreeCAD and OpenCASCADE are LGPL" (deck slide 65) | Same rule (§4.2, §9) | Consistent |
| Grafana | Listed with Prometheus and OpenTelemetry, no isolation note (deck slides 62, 96) | AGPL, optional, unmodified separate service (§4.2, §9) | L6 |
| DWG converter | "ODA converter for DWG" as a licence prerequisite (deck slides 35, 90) | LibreDWG primary; ODA fallback only after legal review (§4.2, §9) | L3 |
| Parser licences | Parser service: "permissive licences only" (deck slide 62) | Block 1 uses LibreDWG (GPLv3) as an isolated CLI (§4.2) | Not logged in plan-vs-deck.md yet |
| Licence check timing | "Each library is checked for licence in Sprint 1" (deck slide 65) | Phase 0 licence scan (§4 preamble, Phase 0 task 6) | Related to D1 (sprint vs phase timeline). Licence-check timing itself is not logged in plan-vs-deck.md |
| Models to host, with their licences | Decision needed before Sprint 1 (deck slide 91) | Watch-list: check per model before deployment (§9) | OD-24 |

### As built in Phase 2 (2026-11-25)

| Component | Licence as installed | How it is used |
|---|---|---|
| LibreDWG 0.14 (official Windows build; 0.11 from conda-forge as fallback) | GPLv3 | Separate processes (`dwg2dxf`; `dxf2dwg`, `dwgread`, `dwgwrite` for test files only) with a time limit, outside the Python environment (`tools/`, git-ignored). No containers in the POC (OD-21, OD-49) |
| cadquery-ocp (OCCT) | LGPL 2.1 with exception (plan §4.2) | Unmodified library. Needs VTK (BSD) at import |
| pypdfium2 | Metadata: "BSD-3-Clause, Apache-2.0, dependency licenses" | Scoped exception in `license_policy.toml` after reading the bundled licence files (FreeType under the FTL; ICU's GPL text is the Autoconf exception only). Pending OD-31 |
| trimesh | MIT | Library |
| opencv-python-headless 5.1 (scan clean-up, ADR-0007) | Apache 2.0 (metadata). `LICENSE-3RD-PARTY.txt` reviewed 2026-11-25: FFmpeg and its codecs are LGPL 2.1, the rest permissive (libpng, zlib, libjpeg, libwebp, ...); no GPL | Library; the bundled LGPL libraries are used unmodified (LGPL rule); the video module is not used |
| LiteLLM 1.111.0 (Model Gateway, ADR-0009) | MIT (`License-Expression`); its LICENSE carves out a `litellm/enterprise/` folder, which the installed wheel does not contain | Library, in-process. Four dependencies pass through reviewed exceptions: python-dateutil (Apache-2.0 / BSD-3-Clause), regex (Apache-2.0 AND CNRI-Python, pending OD-31), tiktoken (MIT text in the License field), tokenizers (unversioned Apache classifier; bundled crates all permissive per its SBOM) |
| matplotlib | Declared by VTK; bundles licence text the gate refuses to waive | Not installed: excluded by `override-dependencies` in the root `pyproject.toml`. Nothing here imports it |

## 4. Deck tools not yet in the plan

The deck names these tools. The plan does not list them, so the plan gives no licence for them. **They are not yet licence-checked.** Each one goes through the Phase 0 licence check before use (plan §4 preamble, §9; plan-vs-deck.md §3).

| Tool | Deck slide | Related difference | Licence |
|---|---|---|---|
| Tesseract | 62 | L1 | Not yet licence-checked |
| OCRmyPDF | 62 | L1 | Not yet licence-checked |
| pypdf | 62 | L1 | Not yet licence-checked |
| Airflow | 62 | L2 | Not yet licence-checked |
| Dagster | 62 | L2 | Not yet licence-checked |
| DeepXDE | 65 | D9, OD-16 | Not yet licence-checked |
| NVIDIA Modulus | 65 | D9, OD-16 | Not yet licence-checked |
| ONNX Runtime | 65 | D9, OD-16 | Not yet licence-checked |
| OpenVINO | 65 | D9, OD-16 | Not yet licence-checked |
| python-pptx | 65 | Not logged | Not yet licence-checked |
| AWS Bedrock | 62 | D6, OD-11 | Hosted service; terms not yet checked |

## 5. How CI enforces the policy

| Piece | What it does |
|---|---|
| `scripts/ci/license_policy.toml` | Lists licence ids per category: `allowed`, `conditional`, `denied_in_process`, plus `[exceptions]` (numpy, sqlite-vec and pypdfium2 at the time of writing, each with the metadata quoted) |
| `scripts/ci/src/edp_ci/license_gate.py` | Reads the licence of every distribution installed in the Python environment it runs in, maps it to an SPDX-like id, classifies it, prints a table, and exits 1 on any `denied_in_process` or unexplained `unknown` result. It skips the workspace's own packages by exact name, read from `[tool.uv.workspace] members` in the root `pyproject.toml` |
| `scripts/ci/tests/test_ci_license_gate.py` | Tests on synthetic metadata: an AGPL distribution fails the gate, LGPL warns, unknown fails, `OR` and `AND` expressions resolve correctly, an unmappable first field is not overridden by a classifier, a `License: UNKNOWN` placeholder is treated as absent, an AGPL classifier next to an unmappable one stays denied, "with" in free text (for example "Apache 2.0 with Commons Clause") is unknown, exceptions clear only unknown results and never GPL, AGPL, SSPL, BSL or RSAL text, workspace packages are skipped by exact name, `--repo-root` sets the policy and workspace. One integration test runs the gate on the current environment |
| `scripts/ci/run_ci.sh` | Runs lint, type check, tests, the licence gate, then Syft (SBOM) and ScanCode if they are installed |

Details of the decision rules are in [scripts/ci/README.md](../../scripts/ci/README.md).

Rules worth knowing:

- An `[exceptions]` entry only clears an `unknown` result. It never clears a licence the gate recognises as denied (GPL, AGPL, SSPL, RSAL, BUSL).
- The gate also ignores an exception when any segment of a licence field or classifier names GPL, AGPL, Affero or "General Public License" (without "Lesser" or "Library" in the same segment), or SSPL, BSL, BUSL, "Business Source License" or RSAL (plan §9 watch-list). This is a text match. Text it does not catch still shows as `unknown`, so reviewers must read the metadata before adding an exception. Never add GPL, AGPL, SSPL, BSL/BUSL or RSAL packages to the exception list.
- The gate uses the first licence field that is present: `License-Expression`, then a short `License`, then the classifiers. A `License` value that is empty or `UNKNOWN` counts as absent. If the field used cannot be mapped, the result is `unknown`; a later field never overrides it.
- `X WITH E` is read only in a `License-Expression`, and only when `E` is a known SPDX exception id (`OCCT-exception-1.0`, for plan §4.2 "OCCT is LGPL 2.1 with exception"; the plan does not give the id). Otherwise the result is `unknown`, or stays denied if `X` is denied.
- `LGPL` passes with a warning. The gate cannot see whether the library was modified; that is a code review item.
- The gate checks the Python distributions installed in the environment it runs in. Each service environment must run it separately (see "What the gate does not cover").

### What the gate does not cover

| Not covered | Covered by | Status |
|---|---|---|
| GPL and AGPL tools run as CLIs or containers (LibreDWG, OpenSCAD, Gmsh, CalculiX, Code_Aster, Neo4j, Grafana) | Container images and an SBOM per image (Syft), ScanCode (plan §4.3) | Not installed on the development machine. Container build blocked by OD-21 |
| Console packages (React and the rest of plan §4.3) | ScanCode or Syft on the console tree | No console code yet |
| Model weights and datasets | Manual check per model and dataset (watch-list) | OD-24 |
| Each block service's own environment | Run the gate inside each block's environment or image. Outside a repo checkout (for example a wheel install in an image), pass `--repo-root` or `--policy`; without a policy file the gate exits 2 | Not specified in plan or deck; TBD when block services exist |
| Source-level licence scan of the candidate stack | ScanCode Toolkit (plan Phase 0 task 6) | Not run yet; scan command TBD in Phase 0 |
| Vulnerability scan | Trivy (plan §4.3) | Not wired. Plan Phase 0 task 5 does not list it; deck slide 62 mentions "vulnerability checks" |

The R1 release gate needs "Zero unresolved AGPL findings; SBOM published" (plan §6, Phase 6). The SBOM step exists in `run_ci.sh` but is skipped until Syft is installed.

## 6. Open items

| Item | Ref |
|---|---|
| Confirm `PSF-2.0` and `ISC` as allowed; they are not named in plan §9 | This document, section 1 |
| Unversioned classifiers: "BSD License" is mapped to `BSD` and allowed, while "Apache Software License" and "Python Software Foundation License" are not mapped and fail as `unknown`. Confirm this split, together with `PSF-2.0` and `ISC` | Plan §9 says "BSD" without a variant and names Apache 2.0 only |
| Confirm the watch-list-derived ids `SSPL`, `SSPL-1.0`, `BUSL`, `BUSL-1.0`, `BUSL-1.1`, `RSAL`, and the GPL ids `GPL-1.0-only`, `GPL-1.0-or-later`, in `denied_in_process` | Plan §9 watch-list and policy text |
| Confirm the SPDX exception list accepted after `WITH` (`OCCT-exception-1.0` only) | Plan §4.2 OCCT row |
| Classify EPL 2.0 (Eclipse Ditto, plan §4.2); it is not in the §9 policy classes | Plan §4.2, §9 |
| Confirm every licence in plan §4 with the scan and legal | Plan §4 preamble |
| Run the first ScanCode scan on the candidate stack | Plan Phase 0 task 6 |
| Install Syft and ScanCode Toolkit on the CI runner; decide on Trivy | Plan §4.3; OD-18 |
| Pick the CI provider | OD-18 |
| Hosted, on-premises, or both; this sets how strictly GPL is isolated | OD-2 |
| Models to host, with their licences | OD-24, OD-11 |
| Licence check for the deck-only tools in section 4 | Plan-vs-deck L1, L2, D6, D9 |

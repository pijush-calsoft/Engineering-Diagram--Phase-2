# Phase 2 log: Drawing Parser

| | |
|---|---|
| Plan reference | plan §6 Phase 2 (5 weeks, R1) |
| Status | Mostly done. Every R1 input is built and evaluated on synthetic sets; scans miss the dimension F1 target (0.80 vs 0.85); calibration needs real drawings |
| Last updated | 2026-11-25 |

## 1. Order of work

Plan §10 risk 1 mitigation: "scope R1 to vector inputs first and scans second". DXF came first because it can be built and measured now against the synthetic golden set. Phase 1 items that wait on owner inputs (Model Gateway, console, MCP) stay open in [phase-1.md](phase-1.md).

## 2. What was built

| Item | Where |
|---|---|
| `edp-b1-parser` package, `DrawingParser` block, registered through the `edp.blocks` entry point (plan §3) | `blocks/b1_parser/` |
| DXF extraction: layouts, inserts and polylines resolved, DIMENSION values, title block, units, locators with bounding boxes, flags | `edp_b1_parser.dxf`, `edp_b1_parser.title_block` |
| `ArtifactStore` interface; `FabricStore.write()` puts block outputs in the cleaned zone | `edp_kit.storage`, `edp_fabric.store` |
| Parser evaluation suite on the golden set, per profile and family, against the plan Phase 2 targets | `edp_eval.suites.parser_dxf` |
| `--real-blocks` on the orchestrator CLI: entry-point blocks replace stubs | `edp_orchestrator.__main__` |

Phase 2 key tasks (plan):

| # | Task | Status |
|---|---|---|
| 1 | Unified `geometry` artifact | **Done for DXF** |
| 2 | Dimension association to features | **Done in Phase 3 work** (block 2, `recognise.py`); scored by `edp_eval.suites.interpretation` |
| 3 | Title block extraction with per-field confidence | **Done for "LABEL: value" text and block attributes** |
| 4 | Fine-tune symbol detector | **Dropped** (OD-5, OD-38, ADR-0007) |
| 5 | Confidence calibration | Measured (ECE). Starting values 1.0 / 0.5 not yet calibrated on varied data |
| 6 | Render parsed result to SVG for the console | Not started |

## 3. Results on the golden set (80 synthetic DXF, 2026-11-25)

```text
uv run python -m edp_eval.suites.parser_dxf --golden eval/golden/data/synthetic --value-tol 1e-6 --n-bins 10
dimension_f1 1.0 | title_block_accuracy 1.0 | locator_coverage 1.0 | ece 0.0   (all four groups the same)
```

The run settings `value_tol = 1e-6` and `n_bins = 10` are this run's choice. The plan sets neither; both stay open in [eval/README.md](../../eval/README.md).

**These scores do not show the parser is ready.** The synthetic set is easy for it: the same library wrote it, the title blocks use exactly the "LABEL: value" form the rule reads, and nothing is overridden, missing or noisy. What the run shows is that every dimension value, handle and title-block field survives the round trip. The tests add cases the set lacks: overridden dimension text, rounding, conflicting title-block values, unit mismatches, block inserts, polylines, paper-space layouts, unsupported entities, CRLF files. A harder golden set is needed: varied title-block layouts, text overrides, real third-party DXF (see [golden-data-sources.md](../reference/golden-data-sources.md)).

## 4. Problems found and fixed

- **CRLF DXF files parsed as empty.** `ezdxf.read` on a decoded text stream returned an empty document, with no error, for files with Windows line endings; the synthetic files have them. Switched to `ezdxf.recover.read` on raw bytes, which also reports repairs (`DXF_RECOVERED` info flag). Covered by a CRLF test.
- **Rounding tolerance.** The first mismatch check allowed one full unit of the last displayed decimal place; it now allows half a unit, the true rounding bound. Covered by a test.

## 5. Verification (2026-11-25)

```text
bash scripts/ci/run_ci.sh: ruff passed; mypy 42 files clean; 197 passed; requirements match uv.lock; licence gate PASSED
uv run python -m edp_orchestrator --file eval/golden/data/synthetic/syn-asme-bracket-003.dxf --data-dir var --real-blocks
  real blocks: ['b1_parser']; run completed; geometry artifact in the cleaned zone (28 entities, units in)
```

## 6. Rest of Phase 2: DWG, vector PDF, STEP, IGES, STL (2026-11-25)

### Inputs added

| Input | How (plan §4.2 Block 1, plan §6 Phase 2) | Result on the synthetic sets |
|---|---|---|
| DWG | LibreDWG 0.11 `dwg2dxf` as a separate process, then the DXF path | 80 DWG (the DXF set converted): same scores as DXF; entity handles kept |
| Vector PDF | pypdfium2 path segments and text runs; units and scale from the title block | 80 PDF (the DXF set redrawn): dimension F1 1.0 (matched by value and position), title block 1.0 |
| STEP, IGES | OCP topology walk; holes are full cylinders around an axis outside the material; STEP entity ids (`#n`) and IGES directory entries (`DEn`) as locators | 20 STEP: holes recall and precision 1.0, bbox error 5e-8 mm. IGES covered by tests |
| STL | trimesh: bbox, watertightness, volume, through-opening hint from the genus; flagged lossy and unit-less | 20 STL: all watertight, hint right for 20 of 20 |

Contract: `geometry` schema 0.2.0 adds `solids` (`Solid`, `Hole3D`); additive, so the contract stays v0.1 (plan §3). New golden sets (git-ignored, regenerated by command): `synthetic-dwg`, `synthetic-pdf` (with `.pdfmap.json` sidecars), `models` (20 models as STEP and STL with `.model.json` labels; counts toward the Phase 0 "20 STEP/STL" item). New suite: `edp_eval.suites.models` (reports only; no plan targets for 3D inputs, TBD-AC-1). The console lists samples of every format and shows a 3D summary for models.

### Problems found and how they were handled

1. **No LibreDWG binary reachable.** GitHub release downloads reset the connection; GNU mirrors carry only source; nothing on PyPI; no compiler here. conda-forge has LibreDWG **0.11** for Windows; it is installed into an isolated environment under the git-ignored `tools/` ([setup guide](../setup/local-environment.md) §2). OD-49.
2. **Plan says "isolated container"** for `dwg2dxf`; there is no container runtime yet (OD-21), so it runs as a separate process with a time limit (OD-48). Still out of process, as plan §9 requires for GPL.
3. **LibreDWG 0.11 writes damaged DXF.** Its XDATA is malformed (ezdxf rejects the file) and its dimension geometry blocks are invalid (ezdxf's auditor deletes every dimension). The DXF reader now strips invalid XDATA and reads such dimensions from their own tags (`dxf_raw.py`). Both are flagged `DXF_RECOVERED`, and both help any damaged DXF.
4. **LibreDWG 0.11 cannot import our MTEXT** (rotation, group code 50) when making test DWGs. The fixture writer rewrites the rotation as a text direction vector before `dxf2dwg`; geometry and labels are unchanged.
5. **Licences.** pdfplumber and reportlab were not used (both pull in Pillow); test PDFs come from a small built-in writer. pypdfium2's metadata ("BSD-3-Clause, Apache-2.0, dependency licenses") was checked against its bundled licence files: FreeType under the FTL; ICU's GPL text is only the Autoconf build-script exception. It passes through a scoped exception, pending OD-31. cadquery-ocp needs VTK at import, and VTK declares matplotlib, whose bundled licence text the gate correctly refuses to waive. matplotlib is not needed, so a uv override excludes it (this also drops Pillow). OCCT inside cadquery-ocp is LGPL 2.1 with exception, used unmodified (plan §4.2 Block 5).
6. **Arcs drawn as one Bezier** were lost; fixed by evaluating the curve at t = 0.5 to get a third point.
7. **Slot ends counted as holes** in STEP (half cylinders); holes now need a full turn around their axis.
8. **Fitted PDF circles** differ from true diameters by about 0.0002 mm, because the writer rounds coordinates to 0.001 pt; tests compare at 0.001 mm.

### Verification

```text
bash scripts/ci/run_ci.sh: exit 0. ruff passed; mypy 62 files clean; 231 passed; requirements in sync;
  licence gate 74 distributions: 71 pass, 3 recorded exceptions (numpy, sqlite-vec, pypdfium2), 0 fail;
  npm licence gate 100 packages; console type check passed
Suites: parser_dxf on synthetic, synthetic-dwg, synthetic-pdf; interpretation on synthetic-dwg (1.0); models (above)
Console: STEP, PDF and DWG samples run through blocks 1 to 3; screenshots of the STEP and PDF runs reviewed
```

### Known limits

- The sets are easy: generated here, PDFs from a simple writer (Helvetica, whole words), DWGs converted from the DXF set. Real exports split text into characters, draw text as outlines, use dashed and hidden lines, and come from many CAD tools.
- PDF dimensions have no measured points, and PDF outlines are plain paths, so block 2 does not yet link PDF dimensions to features ([phase-3.md](phase-3.md) open items).
- Block 2 does not yet build features from 3D topology.

## 7. LibreDWG 0.14 (2026-11-25, OD-49)

The owner downloaded the official 0.14 Windows build to `tools/libredwg-0.14-win64/`. Findings:

| Check | Result |
|---|---|
| 0.14 reading the old DWG set (written by 0.11) | Fails: buffer overflows, no entities. 0.11 reads DWGs written by 0.14, so 0.11's writer is at fault |
| 0.14 round trip (0.14 writes, 0.14 reads) | Entities, title block and dimension values right, but 224 false `DIM_TEXT_MISMATCH` flags and dimension association 0.85 |
| Cause | `dwgread` JSON of the DWG shows `oblique_angle` = 90° and `dim_rotation` = 0 for vertical dimensions: 0.14's DXF import stores DXF group code 50 (rotation) as the oblique angle, and rejects code 52. The parser was right to flag them |
| Fix (test files only) | `edp_eval.synth.dwg` compares the written DWG with the source DXF by handle and, when they differ, sets the angles in the `dwgread` JSON and rewrites the DWG with `dwgwrite` |
| After the fix | `synthetic-dwg` regenerated with 0.14: parser dimension F1, title block and locators 1.0; interpretation feature recall, precision and dimension association 1.0, 0 flags |

The parser now prefers 0.14 (`edp_b1_parser.dwg`), with 0.11 as fallback. All of this tests LibreDWG against itself; DWGs from commercial CAD tools are still needed (OD-7).

## 8. Phase 2 status by task

| Task (plan §6 Phase 2) | Status |
|---|---|
| 1 Unified geometry artifact | Done for every R1 input except scans |
| 2 Dimension association | Done for DXF and DWG (in block 2); PDF and 3D pending |
| 3 Title block | Done for DXF, DWG and PDF text |
| 4 Symbol detector fine-tune | Dropped (OD-5, OD-38, ADR-0007) |
| 5 Calibration | Measured on synthetic sets only; needs real drawings (OD-7) |
| 6 Rendering for the console | Done: the console redraws the geometry artifact as SVG |
| Scans | Built 2026-11-25 (§9); title block, locators and ECE meet the scan targets on 20 synthetic scans, dimension F1 does not (0.80 vs 0.85) |

## 9. Scans (2026-11-25, ADR-0007)

Plan Phase 2 "Scans": "OpenCV deskew and denoise, line and circle detection, PaddleOCR or docTR for text, RT-DETR or D-FINE ... VLM for title block and notes". ADR-0007 replaces the OCR and detector models with a multimodal model over the API.

### Built

| Item | Detail |
|---|---|
| `edp_b1_parser.scan` | Pages: image files, or the largest image on each PDF page at its own resolution. Clean-up: 3-pixel median filter; deskew by the median angle of long lines within 10 degrees of level (OD-52). One gpt-5.5 vision call per page (prompt `scan-read-1`) returns title block, dimensions and notes, each with a box and a confidence. Code checks: box inside the page with an area, value is a number in the text; failures flagged `LOW_CONFIDENCE` or `DIM_TEXT_MISMATCH`. Boxes mapped back through the deskew; locators in image pixels, y up |
| Block 1 | Accepts `image`; PDFs flagged `SCANNED_PDF` go to the scan path. The run's `data_class` (new orchestrator run parameter) decides: client scans are refused by the gateway (`SCAN_NOT_READ`, blocking) until title-block masking exists (OD-51) |
| Orchestrator | `start(run_id, inputs, params)`; params reach every block. Console samples are `synthetic`, uploads `client` |
| Golden data | `synthetic-scan`: the 80 vector PDFs rendered at 150 DPI, rotated up to 2 degrees, blurred, with grain noise; `.scanmap.json` gives each truth dimension's text position in image pixels (checked by overlaying it on a scan) |
| Suite | `edp_eval.suites.parser_scan`, `--limit K` spreads K drawings over the set (each costs a model call) |
| Licence | opencv-python-headless 5.1 (Apache 2.0); it bundles FFmpeg and codecs under LGPL 2.1 as unmodified libraries (LGPL rule, plan §9); no GPL part |

### Results (20 of 80 synthetic scans, live)

| Metric (plan Phase 2, scans column) | 20 synthetic scans | Target | Met |
|---|---|---|---|
| Dimension value and target F1 | 0.80 | >= 0.85 | No |
| Title block field accuracy | 0.96 | >= 0.92 | Yes |
| Entities with a valid locator | 1.00 | 100 % | Yes |
| Calibration error (ECE) | 0.078 | <= 0.08 | Yes, barely |

Every scan returned as many dimensions as it has, so the misses are wrong values or far boxes, not missed reads. Re-reading the two worst scans showed both: digits misread in 15-pixel text (9 read as 8, 55 as 65, 3 as 4, 4.5 as 4, 6.6 as 8) and boxes 20 to 36 pixels from the text centre (the match allows two text heights, 30 pixels). ISO drawings scored lower than ASME. Title-block errors: one field on 5 of 20 drawings (a console run also read EDP-SYN-0000 as EDR-SYN-0000). Deskew found the rotation within 0.2 degrees when long lines exist; on 5 drawings without long enough lines it found none, and the reading still worked.

Cost: 1.97 USD for 20 pages, about 4,800 input and 2,300 output tokens per page; output is mostly the model's reasoning (OD-53). About 30 to 120 seconds per page.

### Not built, and next steps

- Higher resolution or tiling for small text (the next thing to try against the F1 gap), and saving each reading in the suite output for diagnosis.
- Line and circle detection (plan), so block 2 can find features on scans.
- GD&T frames and symbols.
- Calibration of the model's confidences (task 5); title-block masking for client scans (OD-51).

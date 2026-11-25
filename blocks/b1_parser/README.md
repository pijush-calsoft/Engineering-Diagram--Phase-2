# Block 1: Drawing Parser

**Status: Phase 2 in progress. DXF path built**, registered as `b1_parser` through the `edp.blocks` entry point (plan §3).

Extracts geometry, dimensions, the title block and source locators. Output: `geometry` artifact, written to the Data Fabric's cleaned zone (deck slide 30).

## By input

| Input | Method | Status |
|---|---|---|
| DXF | ezdxf `recover.read` (handles CRLF, encodings, damaged files); model space and every layout; polylines and block inserts resolved to parts that keep the source handle; DIMENSION displayed value and measurement | **Built** |
| DWG | LibreDWG `dwg2dxf` as an isolated CLI (GPLv3), then the DXF path | Not started |
| Vector PDF | pdfplumber / pypdfium2 | Not started |
| STEP, IGES | OCP / pythonocc-core | Not started |
| STL | trimesh | Not started |
| Scans | OpenCV + scikit-image pre-processing; OCR, symbols, GD&T and title blocks through a multimodal model over the OpenAI API ([ADR-0007](../../docs/adr/0007-vision-via-multimodal-api.md)) | Not started; needs OD-43 |

## What the DXF path reports

| Item | Detail |
|---|---|
| Entities | line, arc, circle, spline, text, dimension (the `geometry` schema). Other types are counted and reported in an `UNSUPPORTED_ENTITY` info flag, never guessed |
| Locator | file id, Fabric commit, layout as view, layer, DXF handle, bounding box in drawing units |
| Dimensions | `value` = number in the displayed text (what the drawing states); `measurement` = geometry. `DIM_TEXT_MISMATCH` review flag when they differ by more than the displayed rounding |
| Title block | "LABEL: value" text and block attributes: part number, revision, material, scale, units, tolerances. Conflicting values give confidence 0.5 and a `LOW_CONFIDENCE` flag |
| Units | DXF `$INSUNITS`; `UNIT_MISMATCH` review flag when the title block says otherwise |
| Status | `needs_review` when any flag needs review, which pauses the orchestrator |

Not built yet: dimension-to-feature association (Phase 2 task 2), view detection inside a layout (views are layouts for now), confidence calibration beyond the starting values (task 5), SVG rendering for the console (task 6).

## Evaluation

```
uv run python -m edp_eval.suites.parser_dxf --golden eval/golden/data/synthetic --value-tol 1e-6 --n-bins 10
```

On the 80 synthetic drawings (2026-11-25): dimension F1 1.0, title-block accuracy 1.0, valid locators 1.0, ECE 0.0. **This set is easy for this parser.** It was written with the same library, and its title blocks use the exact "LABEL: value" form the rule reads. It shows that values, handles and fields round-trip; it does not predict results on real drawings. See [phase-2.md](../../docs/progress/phase-2.md).

# Phase 2 log: Drawing Parser

| | |
|---|---|
| Plan reference | plan §6 Phase 2 (5 weeks, R1) |
| Status | In progress. DXF path built and evaluated; other inputs and tasks 2, 4 to 6 pending |
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
| 2 | Dimension association to features | Not started. The F1 target is the DIMENSION handle until then |
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

## 6. Next in Phase 2

1. Dimension association (task 2): link each dimension to the entities it measures; extend synthetic labels with the measured entity handles.
2. Harder golden data: title-block variants, overridden texts, rendered vector PDFs.
3. Vector PDF path (pdfplumber / pypdfium2).
4. DWG through LibreDWG `dwg2dxf` as an isolated CLI (needs the binary; GPLv3, separate process per plan §9).
5. STEP / IGES (OCP) and STL (trimesh).
6. SVG rendering for the console (task 6).
7. Scans through the multimodal API (needs `OPENAI_API_KEY` and OD-43).

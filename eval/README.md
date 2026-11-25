# eval: evaluation harness

Evaluation is a cross-cutting track that starts in Phase 0 and never stops (plan §7). This package holds the golden-dataset manifest model, the metric code and the synthetic drawing generator. It holds no data.

## What lives where

| Path | Content | Source |
|---|---|---|
| `golden/` | Dataset manifests. The data itself lives in the Data Fabric | plan Appendix A |
| `suites/` | Per-block and end-to-end evaluation | plan Appendix A |
| `src/edp_eval/golden.py` | Manifest model (`GoldenItem`, `GoldenManifest`) and the Phase 0 golden-set check | plan Phase 0 task 2 and exit criteria, principle 7 |
| `src/edp_eval/metrics.py` | Parser metrics and `PHASE2_TARGETS` | plan Phase 2 exit criteria, plan §7 Parser row |
| `src/edp_eval/suites/parser_dxf.py` | Drawing Parser suite on the DXF golden set: the four Phase 2 metrics, per profile and family | plan §7 Parser row, Phase 2 exit criteria |
| `src/edp_eval/suites/interpretation.py` | Interpretation suite: feature recall and precision, dimension association | plan §7 Interpretation row, Phase 3 exit criteria |
| `src/edp_eval/suites/knowledge_graph.py` | Knowledge Graph suite on the family set: similar-part recall@3, corroboration outcomes | plan §7, Phase 3 exit criteria |
| `src/edp_eval/suites/models.py` | 3D suite: STEP holes, bounding box and volume; STL watertightness and opening hint. Reports only | plan Phase 2; no 3D targets in the plan (TBD-AC-1) |
| `src/edp_eval/synth/` | Synthetic DXF drawings with exact labels, ISO and ASME profiles | OD-7, OD-1 (owner answers 2026-11-24) |
| `tests/` | Unit tests with hand-computed values | plan §4.3 Testing (pytest) |

Golden data lives in the Data Fabric, not in the repo (plan Appendix A: "golden/ # dataset manifests (data lives in the fabric)"). Keeping drawings, models and labels out of git is a repo rule, stated in the root `.gitignore`. Client data has a further rule: it stays in client scope (plan principle 7). The root `.gitignore` excludes exactly these patterns: `eval/golden/data/`, `*.dwg`, `*.dxf`, `*.step`, `*.stp`, `*.stl`, `*.igs`, `*.iges`, `*.frd`. It re-includes `eval/golden/fixtures/**`, so files there can be committed. Scans (PNG, TIFF, JPEG), PDFs and label files are not excluded by extension. Golden data must therefore live only under `eval/golden/data/`.

## Status

| Item | Status | Source |
|---|---|---|
| Golden manifest model with provenance rules | Done | plan Phase 0 task 2, principle 7 |
| Phase 0 check: at least 60 labelled drawings | Done (`GoldenManifest.phase0_exit_check()`). Counts internal and openly licensed items only; client-scoped items are reported separately | plan Phase 0 exit criteria, Phase 0 task 2 |
| Report on 20 STEP/STL models target | Done (reported, does not affect pass/fail) | plan Phase 0 task 2 |
| Report on "60 to 100 drawings" range | Done for all drawings and for labelled drawings (information only, does not affect pass/fail). Which reading applies: not specified in plan or deck; TBD in Phase 0 | plan Phase 0 task 2 |
| Dimension F1, title block accuracy, locator coverage, ECE | Done (functions only, no data) | plan Phase 2 exit table, §7 |
| Golden dataset v1, vector DXF slice | **Done: 80 synthetic drawings** (seed 2026), all labelled and self-verified. Generated locally under `eval/golden/data/synthetic/`; not in git | OD-7 (decided), plan Phase 0 task 2 |
| Vector PDF and scan slices | Pending: render from the synthetic DXF, plus public sources after licence sign-off ([golden-data-sources.md](../docs/reference/golden-data-sources.md)) | plan Phase 0 task 2 |
| 20 STEP/STL models | Pending: NIST MBE PMI and FreeCAD-library candidates, after licence sign-off | plan Phase 0 task 2 |
| Labelling in Label Studio | Pending | plan Phase 0 deliverables ("golden dataset v1 in Label Studio") |
| Loader from the label export to the metric inputs | Pending. Label export format: not specified in plan or deck; TBD in Phase 0 | Open item below |
| Fast subset on every pull request | Pending (unit tests only for now) | plan §7 |
| Full golden-set suite nightly, gating releases | Pending | plan §7 |
| Metrics for Interpretation/KG, Generation, Solvers, Surrogate, Reports, Orchestrator, Gateway | Pending, in their phases | plan §7 table |

## Synthetic golden set (OD-7)

The owner confirmed there is no internal drawing set (OD-7, 2026-11-24), so the generator creates one. Labels are exact by construction: each value is the parameter the geometry was drawn from, and every label carries the DXF handle of its entity as the source locator (plan principle 1, Phase 2 task 1).

| Aspect | What the generator does | Source |
|---|---|---|
| Part families | Prismatic plate (hole pattern, optional slot) and sheet-metal L-bracket (bend radius, hole) | plan Phase 0 task 3 recommendation; working assumption for OD-12 |
| Standards | `iso` profile: first-angle projection, mm. `asme` profile: third-angle projection, inches | OD-1 "try both"; details open as OD-41 |
| Views | Front view and view from above, placed by projection method | |
| Labels | Dimensions (target, value, kind, view, handle), title block (part number, revision, material, scale, units, general tolerance; each with its TEXT handle), parameters | plan Phase 0 task 2 label categories |
| Self-check | Every drawing is re-read after writing. Each DIMENSION's measured geometry **and displayed text** must equal its label, and each title-block TEXT must hold its value | |

Parameter ranges, materials and tolerance notes are generator settings, not plan values. Labelled categories per item: `dimensions`, `title_block`, `material`, `expected_parameters`. `geometry` and `tolerances` are not claimed, because entity-level geometry and per-feature tolerances are not labelled.

Generate the set (output stays under the git-ignored `eval/golden/data/`):

```
uv run python -m edp_eval.synth --out eval/golden/data/synthetic --count 80 --seed 2026 --uri-prefix s3://edp-fabric/golden/synthetic
```

`--uri-prefix` is where the files will live once the Data Fabric exists (Phase 1); the bucket name is a placeholder until then. The same seed and count always give the same set.

## Using the code

```python
from edp_eval.golden import GoldenManifest
from edp_eval.metrics import PHASE2_TARGETS, dimension_f1

manifest = GoldenManifest.from_json_file("eval/golden/manifest.example.json")
check = manifest.phase0_exit_check()       # counts and passed flag

r = dimension_f1(predicted, truth, value_tol=...)   # tolerance has no default; see open items
PHASE2_TARGETS["dimension_f1"].met(r.f1, "vector")
```

Run the tests:

```
uv run pytest eval/tests
uv run ruff check eval
uv run mypy eval/src
```

## Targets

`PHASE2_TARGETS` copies the plan Phase 2 exit table. Plan §7: "Targets in section 6 are proposals to confirm in Phase 0."

| Metric | Vector DXF / PDF | Scans |
|---|---|---|
| Dimension value and target F1 | ≥ 0.95 | ≥ 0.85 |
| Title block field accuracy | ≥ 0.98 | ≥ 0.92 |
| Entities with a valid source locator | 100 % | 100 % |
| Calibration error (ECE) on confidences | ≤ 0.05 | ≤ 0.08 |

The table has no column for DWG, STEP, IGES or STL. DWG goes through the DXF path (plan Phase 2 "Approach by input"), but which column applies to it is not specified in plan or deck; TBD in Phase 0.

## Metric behaviour to know

- `dimension_f1` uses greedy one-to-one matching. Greedy is not a maximum matching. It can undercount true positives, and when value differences tie the result depends on the order of the predictions. `test_dimension_f1_greedy_is_order_dependent_on_ties` shows a case. The plan does not give a matching algorithm (plan Phase 2 exit table).
- Empty predictions do not raise. `dimension_f1` with no predictions returns 0.0 for precision, recall and F1. `title_block_accuracy` with an empty prediction returns 0.0. Only an empty truth raises `ValueError`. This is a design choice: a parser that finds nothing scores 0 and the run goes on. Not specified in plan or deck; TBD in Phase 0.
- `locator_coverage` is meant for raw parser output. `GeometryEntity` in `contracts/` declares `locator` as required, so validated entities always score 1.0.
- `expected_calibration_error` finds the bin by comparing with the edges `i / n_bins`, so values on a bin edge (for example 0.57 with `n_bins=100`) land in the right bin.

## Open items

| Item | Where it is tracked |
|---|---|
| Internal drawing set for the golden dataset | OD-7 |
| Golden data source: internal or openly licensed (plan) or the customer's set (deck slide 90, "50 to 100 drawings") | OD-17, plan-vs-deck D10. Code follows the plan |
| Part families for R1; `part_family` stays a free string until decided | OD-1, OD-12 |
| Block In/Out lines for acceptance criteria (Phase 0 task 1) | OD-14 |
| Client-scoped items: the code counts only internal and openly licensed items toward the Phase 0 exit (plan Phase 0 task 2). Client items are reported in `client_*` fields | Follows the plan. Linked to OD-7, OD-17 |
| Dimension matching algorithm (greedy or maximum matching) and tolerance (`value_tol`). Not specified in plan or deck | TBD in Phase 0 |
| What counts as "labelled" for the Phase 0 exit: which `label_fields` must be present. Not specified in plan or deck. The code counts any item with `labelled: true` and at least one field, and reports counts per field | TBD in Phase 0 |
| Whether the "internal or openly licensed" rule also covers the 20 STEP/STL models (the plan sentence names drawings). The code applies it to models too | TBD in Phase 0 |
| ECE bin count (`n_bins`). Not specified in plan or deck | TBD in Phase 0 |
| Which Phase 2 target column applies to DWG and 3D inputs | Not specified in plan or deck; TBD in Phase 0 |
| Whether the "60 to 100 drawings" range (plan Phase 0 task 2) applies to all drawings or to labelled drawings. Not specified in plan or deck. The code reports both | TBD in Phase 0 |
| Label export format, and the loader from it to the metric inputs. Plan Phase 0 deliverables name only "golden dataset v1 in Label Studio". Not specified in plan or deck | TBD in Phase 0 |
| Empty predictions score 0 and do not raise. Not specified in plan or deck | TBD in Phase 0 |
| Which tests form the "fast subset" run on every pull request (plan §7). Not specified in plan or deck | TBD in Phase 0 |
| Whether "valid" locator means more than present (for example, resolves to a Fabric file version) | Not specified in plan or deck; TBD in Phase 0 |

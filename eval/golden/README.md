# eval/golden: golden-dataset manifests

This folder holds dataset manifests only. The drawings, models and labels live in the Data Fabric (plan Appendix A: "data lives in the fabric"). Keeping them out of git is a repo rule, stated in the root `.gitignore`; client data also stays in client scope (plan principle 7). `eval/golden/data/` is in `.gitignore`. Scans, PDFs and label files are not excluded by extension, so any local golden data must live only under `eval/golden/data/`. `eval/golden/fixtures/**` is re-included and can be committed.

## What the plan asks for

| Item | Plan says | Source |
|---|---|---|
| Drawings | 60 to 100 across DXF, DWG, vector PDF and scans | plan Phase 0 task 2 |
| 3D models | 20 STEP/STL | plan Phase 0 task 2 |
| Ground truth | Hand-labelled: geometry, dimensions, tolerances, title block fields, material, expected parameters | plan Phase 0 task 2 |
| Allowed sources | Internal or openly licensed drawings; client drawings only inside that client's scope | plan Phase 0 task 2, principle 7 |
| Deliverable | Golden dataset v1 in Label Studio | plan Phase 0 deliverables |
| Exit criterion | At least 60 labelled drawings | plan Phase 0 exit criteria |

The deck asks instead for "50 to 100 drawings with known dimensions, plus STEP assemblies" from the customer architect (deck slide 90). The plan is followed here; the difference is D10, decision OD-17.

## Manifest format

Model: `edp_eval.golden.GoldenManifest`. Example: [manifest.example.json](manifest.example.json). The example items are fake and point at no real data. The example holds only internal and openly licensed items; client-scoped items are covered in the tests, not in this shared example (principle 7).

| Field | Meaning | Rule |
|---|---|---|
| `version` | Manifest version | Free string |
| `items[].id` | Item id | Stripped; not blank; unique in the manifest |
| `items[].input_format` | `dxf`, `dwg`, `pdf_vector`, `scan`, `step`, `iges`, `stl` | R1 input types (plan §2.1, Phase 2) |
| `items[].part_family` | Part family | Stripped; not blank. Free string until OD-1 / OD-12 are decided |
| `items[].provenance.kind` | `internal`, `open` or `client` | plan Phase 0 task 2 |
| `items[].provenance.licence` | Licence of an openly licensed item | Required when kind is `open` |
| `items[].provenance.client_scope` | Opaque scope tag | Required when kind is `client`; rejected for other kinds. Never a client name (principle 7) |
| `items[].data_uri` | Location in the Data Fabric | Must start with `s3://` (plan §3, `Artifact.uri` comment). The non-blank path and no-surrounding-spaces checks are a validation choice: not specified in plan or deck; TBD in Phase 0 |
| `items[].ground_truth_uri` | Location of the labels | Optional until labelled; required when `labelled` is true. May be set on an unlabelled item (labels in progress) |
| `items[].labelled` | Ground truth exists | |
| `items[].label_fields` | Which ground-truth categories are labelled | Values from Phase 0 task 2: `geometry`, `dimensions`, `tolerances`, `title_block`, `material`, `expected_parameters`. At least one when labelled; empty when not labelled; no duplicates |

## Phase 0 check

`GoldenManifest.phase0_exit_check()` returns:

- `labelled_drawings` and `passed` (`labelled_drawings >= 60`). Drawings are `dxf`, `dwg`, `pdf_vector`, `scan`.
- Only items with provenance kind `internal` or `open` count toward the shared numbers. Plan Phase 0 task 2: "Use only internal or openly licensed drawings; client drawings are used only inside that client's scope." Client-scoped items are reported in `client_labelled_drawings` and `client_labelled_models` and never change `passed`.
- `labelled_models` and `models_target_met` (`>= 20`). Only `step` and `stl` count, because the plan's count names STEP/STL only. IGES items are counted in `labelled_by_format` but not as models. The model target is a task-2 target, not an exit criterion, so it does not change `passed`.
- `total_drawings_within_range` and `labelled_drawings_within_range`: whether the shared drawing count, and the shared labelled drawing count, are within "60 to 100 drawings" (plan Phase 0 task 2). Information only; they do not change `passed`. Whether the range applies to all drawings or to labelled drawings: not specified in plan or deck; TBD in Phase 0.
- `labelled_drawings_by_field`: shared labelled drawings per label field.

An item counts as labelled when `labelled` is true; it then has at least one label field. Which label fields must be present for a drawing to count as labelled is not specified in plan or deck; TBD in Phase 0.

This covers only the golden-set part of the Phase 0 exit criteria. Director sign-off and the CI AGPL check are separate.

## Not done yet

- No real manifest. The data source is open (OD-7, OD-17).
- Label Studio project (plan Phase 0 deliverables: "golden dataset v1 in Label Studio").
- Label export format and a loader from it to the metric inputs. Not specified in plan or deck; TBD in Phase 0.
- Checking that a `data_uri` exists in the Fabric (needs the Phase 1 Data Fabric).

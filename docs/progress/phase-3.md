# Phase 3 log: Interpretation and Knowledge Graph

| | |
|---|---|
| Plan reference | plan §6 Phase 3 (4 weeks, R1, overlaps Phase 2) |
| Status | In progress. Interpretation (block 2) built rule-based; Knowledge Graph (block 3) not started |
| Last updated | 2026-11-25 |

## 1. Before Phase 3: dependency incident

While starting Phase 3, the licence gate failed on packages nobody had planned: `openai`, `langchain-openai`, `tiktoken`, `pywin32`, `pillow` and others. Cause: around 10:30 on 2026-11-25 the package `robocrew` (a drone and robotics agent library that pulls in Gemini, Hugging Face and OpenCV) was added to the root `pyproject.toml`. The Phase 2 commit `924e4c3` at 10:33 swept it in through `git add -A`, without a review of the dependency diff. That commit also had a mypy error in the orchestrator CLI, because CI was not re-run after the last edit.

The owner chose to remove it. Commit `96e293d` removes `robocrew` (about 45 packages), regenerates the requirements files and fixes the typing. CI after the fix: 197 tests, licence gate 61 pass with 0 failures. CLAUDE.md now requires a full CI run after the last edit and a read of the dependency diff before every commit.

## 2. What was built

| Item | Where |
|---|---|
| Parser now outputs each dimension's measured points (linear: two points and the axis; diameter and radius: centre) | `edp_b1_parser.dxf._measured_points` |
| Synthetic labels v0.2.0 with an explicit feature list (hole, slot, bend and their parameters); set regenerated, DXF files unchanged | `edp_eval.synth` |
| Block 2 `Interpretation`: rule-based holes, slots and bends; dimension association; design graph; pint units; flags with reason codes | `blocks/b2_interpretation/` |
| Interpretation suite: feature recall and precision, dimension association accuracy | `edp_eval.suites.interpretation` |

Plan Phase 3 Interpretation tasks:

| # | Task | Status |
|---|---|---|
| 1 | Design graph schema | Using contract v0.1 |
| 2 | Feature recognition from 2D (rule-based first) and 3D | **2D rule-based done** for hole, slot, bend; 3D and the LLM path not started |
| 3 | Requirements parsing | Not started (needs LLM, OD-43) |
| 4 | Unit and consistency checks with pint | **Done** for units, contradictions, features outside the outline |
| 5 | Low-confidence flags with a reason code, sent to the KG | **Flags done**; sending to the KG waits for block 3 |

Phase 2 task 2 (dimension association) is done as part of this work.

## 3. Results (80 synthetic drawings, 2026-11-25)

```text
uv run python -m edp_eval.suites.interpretation --golden eval/golden/data/synthetic --value-tol 1e-6
feature_recall 1.0 (plan target >= 0.90) | feature_precision 1.0 | dimension_association 1.0 | flags 0
```

The first run gave dimension association 0.90 (plates 0.82). The cause was the evaluator, not the recogniser: one position dimension locates two aligned holes, and the recogniser links it to both, but the evaluator kept one link and the label names only one hole. The evaluator now counts a dimension as right when any of its links matches the label's owner.

The caveat from Phase 2 applies: the set is clean and generated with the same conventions the rules expect. Unit tests cover undimensioned holes, contradictory dimensions, holes with no outline or outside it, missing units, inch normalisation, vertical slots and bends.

## 4. Verification

```text
bash scripts/ci/run_ci.sh: ruff passed; mypy 47 files clean; 207 passed; requirements match uv.lock; licence gate 65 pass, 2 recorded exceptions, 0 fail
Dependency diff reviewed: edp-b2-interpretation, pint, flexcache, flexparser, platformdirs (all planned)
```

## 5. Next in Phase 3

1. **Knowledge Graph (block 3)**: graph store behind an interface (Apache AGE per ADR-0003 when Postgres runs; local adapter now). Entity relations: part, revision, material from the design graph and title block.
2. Similar-part search: shape descriptors from the design graph now. Text embeddings wait for OD-42.
3. Corroboration: low-confidence flags looked up in similar parts, with evidence and locators.
4. A curated similar-part set for the recall target (plan: top-3 recall ≥ 0.8).
5. Requirements parsing and LLM structured output, once OD-43 is decided and a key is in `.env`.

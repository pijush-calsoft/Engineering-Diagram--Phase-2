# Block 3: Knowledge Graph

**Status: Phase 3 built** with local adapters and a design-graph similarity descriptor. Registered as `b3_knowledge_graph` through the `edp.blocks` entry point (plan §3).

Takes the run's `geometry` (for the title block) and `design_graph`. Finds similar parts already in the graph, corroborates low-confidence values, then adds the drawing to the graph. Output: a `similar_parts` artifact with the similar revisions and every corroboration with its evidence.

## Plan Phase 3, Knowledge Graph tasks

| # | Task | Built | Waiting on |
|---|---|---|---|
| 1 | Graph store: Apache AGE on Postgres or Neo4j Community | `GraphStore` interface; `SqliteGraphStore` local adapter (ADR-0008) | Postgres / AGE when containers run (OD-21); ADR-0003 still Proposed |
| 2 | Relations: part, revision, mating part, material, supplier, load case, test result | Part → Revision → Material, Features, Drawing, from the design graph and title block. `MatingPart`, `Supplier`, `LoadCase`, `TestResult` and their relations are defined | A data source for mating parts, suppliers, load cases and test results |
| 3 | Similar-part search: text embeddings + trimesh shape descriptors | Deterministic descriptor from the design graph: feature counts, overall dimensions and feature parameters in mm; equal-weight score | Embeddings: OD-42. Shape descriptors: 3D input (STEP/STL path, Phase 2) |
| 4 | Corroboration with evidence and locators | Low-confidence values (`geometry_only`) checked against similar parts; evidence keeps the other drawing's locators | |

## How corroboration decides

- Evidence is the same feature (same type, closest in its other parameters) in a similar part, used only where that part dimensioned it.
- Other revisions of the **same part number** decide when there are any; other similar parts are listed as supporting evidence only. Without sibling revisions, similar parts decide and must agree.
- **resolved**: agreeing evidence and none against. Confidence 0.7 + 0.1 per agreeing part, at most 0.95. The run continues, with a `CORROBORATED` info flag.
- **conflict** or **no_evidence**: the value is flagged `LOW_CONFIDENCE` with `[CONFLICTING_EVIDENCE]` or `[NO_EVIDENCE]`, and the run waits for a person (plan principle 3).
- The value is never replaced; corroboration only confirms it or hands it to a person.

Block 2 no longer pauses for low-confidence values on its own: they come here first (plan principle 3).

## Evaluation

```
uv run python -m edp_eval.synth --out eval/golden/data/families --families 24 --revisions 3 --seed 2026 --uri-prefix s3://edp-fabric/golden/families
uv run python -m edp_eval.suites.knowledge_graph --golden eval/golden/data/families
```

On 72 drawings (24 families × 3 revisions; 12 families adversarial, spread over both profiles and part types), 2026-11-25:

| Plan Phase 3 exit criterion | Result |
|---|---|
| Similar-part top-3 recall ≥ 0.8 | 1.0 |
| ≥ 50 % of low-confidence flags correctly resolved | 0.5 (12 of 24) |
| None resolved wrongly above 0.9 confidence | 0 wrong |

The 0.5 share is set by the set's mix: half of the omitted values are adversarial on purpose. The result that does not depend on the mix: all 12 values whose siblings agree were resolved, and all 12 whose siblings disagree were left to a person. As with blocks 1 and 2, the set is generated and clean.

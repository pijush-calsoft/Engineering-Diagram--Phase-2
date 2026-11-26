# Block 2: Interpretation

**Status: Phase 3 in progress. Rule-based recognition from 2D geometry built**, registered as `b2_interpretation` through the `edp.blocks` entry point (plan §3).

Geometry in, `design_graph` out (plan Phase 3). Output goes to the Data Fabric's cleaned zone.

## What it does

| Plan Phase 3 task | Built |
|---|---|
| 1. Design graph schema | Uses `edp_contracts.artifacts.design_graph` v0.1: feature nodes with parameter nodes (`has_parameter`), part-level dimension parameters, material and general-tolerance nodes from the title block |
| 2. Feature recognition, rule-based first | **hole** (circle + diameter dim + position from the outline corner), **slot** (two facing half-arcs), **bend** (two concentric arcs). Also Phase 2 task 2: each dimension is linked to the feature it measures |
| 3. Requirements parsing (Docling + LLM) | Not started: needs the LLM path (OD-43) |
| 4. Unit and consistency checks with pint | `value_mm` on every parameter; `CONTRADICTION`, `FEATURE_OUTSIDE_PART`, `[UNITS_UNKNOWN]` flags; `EMPTY_INTERPRETATION` (review) when no feature or dimension is recognised (OD-62) |
| 5. Low-confidence flags with a reason code | `LOW_CONFIDENCE` with `[UNDIMENSIONED]` or `[NO_DATUM]` |

Each parameter records how its value was found:

| `association` | Meaning | Confidence (starting value) |
|---|---|---|
| `geometric` | a dimension measures this feature's points | 1.0 |
| `by_value` | a dimension has the same value but no geometric link (bend thickness) | 0.9 |
| `geometry_only` | no dimension; value taken from the drawing geometry; flagged | 0.7 |

Not built yet: pocket, boss, fillet and rib features; 3D topology input (STEP); requirements; LLM structured output for intent and notes (ADR-0007, OD-43); sending flags to the Knowledge Graph (block 3).

## Evaluation

```
uv run python -m edp_eval.suites.interpretation --golden eval/golden/data/synthetic --value-tol 1e-6
```

On the 80 synthetic drawings (2026-11-25): feature recall 1.0 (plan target ≥ 0.90), precision 1.0, dimension association 1.0, no flags. The same caveat as block 1 applies: the set is clean and generated, so this shows the rules work on it, not on real drawings. Unit tests cover undimensioned, contradictory, outline-less and unit-less cases.

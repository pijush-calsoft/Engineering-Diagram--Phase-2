# Domain pack: construction

A domain pack carries what is specific to one component family: glossary, drawing templates, validation rules (load cases, standards, checks), prompt library, benchmark golden set, optional domain model and report templates (deck slide 34 and its notes; deck slide 40 Template Registry). This one is for construction steelwork, starting with column base plates (owner direction 2026-11-26).

| File | What it holds | Source of the values | Status |
|---|---|---|---|
| `materials.json` | Steel grades S275JR, S355JR, S355J2: E, nu, minimum yield by thickness, gamma_M0 | EN 10025-2; EN 1993-1-1 sections 3.2.6 and 6.1 | Standard values |
| `load_cases.json` | One uplift case for a base plate under an HEA 200 column | Footprint from EN 10365 nominal sizes; the 100 kN load is **illustrative only** | Replace with project loads (OD-56) |

Used by:

- `edp_eval.synth.construction`: base-plate golden drawings (detailing rules from EN 1090-2 and EN 1993-1-8).
- Block 6 (`edp_b6_solvers`): material card and load cases for the CalculiX run; every margin links to the load-case row here by file hash and case id (plan Phase 5 exit criterion).
- Block 8 (`edp_b8_report`): the report states the pack, its hash and whether any load case is illustrative.

Not yet in the pack: glossary, drawing templates beyond the synthetic generator, prompt library, design-code checks such as bolt bearing and anchor tension, and fin plates or angle cleats.

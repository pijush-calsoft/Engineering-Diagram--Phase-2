# Phase 5 log: Solver Connectors (block 6)

| | |
|---|---|
| Plan reference | plan §6 Phase 5 (6 weeks, R1); deck slides 48, 50, 53 |
| Status | In progress. CalculiX connector with Gmsh meshing, domain-pack material cards and load cases, margins and the Run Store record built; surrogate, DoE, failure envelope and the other connectors not started |
| Last updated | 2026-11-26 |

## 1. What was built

| Item | Where |
|---|---|
| `edp-b6-solvers` block: STEP + design graph to `margins` and `solver_runs` | `blocks/b6_solvers/` |
| Gmsh mesher in its own process, C3D10 in CalculiX node order, mesh quality (minimum and mean scaled Jacobian) | `edp_b6_solvers.gmsh_mesh` |
| CalculiX deck writer, runner and `.dat` reader (von Mises at integration points, displacement at nodes) | `edp_b6_solvers.calculix` |
| Domain-pack loader: files identified by SHA-256; material card by grade and thickness | `edp_b6_solvers.packs`, `domain_packs/construction/` |
| `solver_runs` artifact schema v0.1 (additive; the contract stays v0.1) | `contracts/src/edp_contracts/artifacts/solver_runs.py` |
| Tool setup without containers: CalculiX from conda-forge through micromamba, Gmsh wheel in its own venv, both outside the licence-gated workspace | [setup guide §3a](../setup/local-environment.md) |

## 2. Exit criteria (acceptance-criteria.md §6)

| ID | Status |
|---|---|
| AC-P5-01 benchmark within 3 % of reference | **One case met**: a cantilever tip deflection against Timoshenko beam theory (`test_cantilever_benchmark_within_three_percent`). A NAFEMS-style set and hand-calculated plate cases are still needed (TBD-AC-5) |
| AC-P5-04 every margin links to solver run, load-case row and model version | **Met**: required fields, filled from the run id, the pack file hash with case id, and the STEP URI with its hash |
| AC-P5-02, AC-P5-03 surrogate error and intervals | Not started (block 7) |

## 3. Result on the base-plate drawing (illustrative load)

`con-iso-base_plate-003`: 580 × 290 × 15 mm, S355JR, four Ø30 anchor holes, 100 kN uplift (illustrative, OD-56).

| Quantity | Value |
|---|---|
| Mesh | 34,893 C3D10 elements, 62,584 nodes, size 7.5 to 1.875 mm, minimum scaled Jacobian 0.60 |
| Peak von Mises stress | 986 MPa, near the bore of hole 3 on the bottom face |
| Allowable | 355 MPa (S355JR, t ≤ 16 mm, gamma_M0 = 1.0) |
| Margin | 0.36: `MARGIN_BELOW_ONE` |
| Peak displacement | 2.6 mm |
| Run time | about 8 s meshing, about 70 s CalculiX |

Hand check for plausibility: a 290 × 15 mm strip spanning the 470 mm between anchor lines, simply supported, carrying 100 kN spread over 200 mm, has a bending stress of about 850 MPa (1,080 MPa for a point load). The FE peak of 986 MPa is in that range, so the low margin is real for this illustrative load and not only a mesh artefact.

## 4. Verification

See [phase-4.md](phase-4.md) §5.

## 5. Still open

Mesh convergence (OD-57), more load-case kinds (compression on grout, shear, moment), bolt and grout modelling, code checks (anchor tension, bolt bearing, EN 1993-1-8), Code_Aster, FEniCSx and Ansys import, the surrogate and the failure envelope (block 7), DoE batches.

# Block 6: Solver Connectors

**Status: CalculiX connector built for the construction slice (2026-11-26).** Package `edp_b6_solvers`.

Meshing, solver runs and margins per load case. Outputs: `margins`, and `solver_runs`, the Run Store record (schema in `edp_contracts.artifacts.solver_runs`).

## How a run works

1. The material card and load cases come from the run's domain pack (`domain_packs/<pack>/`, [ADR-0010](../../docs/adr/0010-domain-packs-and-pass-through.md)); the yield strength is chosen by plate thickness.
2. Gmsh meshes the STEP model into C3D10 tetrahedra in its own process (`gmsh_mesh.py`), and mesh quality is recorded.
3. Boundary conditions come from the load case. For `base_plate_uplift`, the anchor bores are fixed, and the column's tension is applied as equal nodal forces over the footprint on the top face.
4. CalculiX runs in its own process. Von Mises stress is read at the integration points, displacement at the nodes.
5. Margin = (f_y / gamma_M0) / peak von Mises stress. Each margin links to the solver run, the load-case row (pack file hash and case id) and the model version (AC-P5-04).

## Benchmark gate

`test_cantilever_benchmark_within_three_percent` models a 200 × 20 × 20 mm cantilever under a 1 kN tip load and compares it with Timoshenko beam theory. It agrees within 3 % (plan Phase 5 exit criterion; AC-P5-01). One case is not a benchmark suite; NAFEMS-style cases are still to be added.

## Connectors (OD-3, decided 2026-11-24: "all solver")

| Folder | Solver | Role | Source | Note |
|---|---|---|---|---|
| `src/edp_b6_solvers/calculix.py` | CalculiX | Default structural solver | plan Phase 5 task 3 | **Built.** GPL: separate process (plan §9); setup guide §3a |
| `code_aster/` | Code_Aster | Cases CalculiX cannot cover | plan Phase 5 task 3 | Not started. GPL: separate process or container |
| `fenicsx/` | FEniCSx | Custom physics | plan Phase 5 task 3 | Not started |
| `ansys_import/` | Ansys result import | Import results from Ansys runs | deck slides 27, 65, 90 | Not started. Needs an Ansys licence (deck slide 90); added by OD-3 |

Not built:
- a mesh convergence study (OD-57);
- contact, bolt preload, nonlinear material;
- fatigue and buckling;
- DoE batches.

Planned stack (plan §4.2): Gmsh / Netgen, CalculiX, Code_Aster, FEniCSx, meshio, PyVista. The deck also names FreeCAD FEM for CalculiX runs (deck slides 20, 65; plan-vs-deck L4).

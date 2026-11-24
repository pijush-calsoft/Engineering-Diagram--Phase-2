# Block 6: Solver Connectors

**Status: not started.** Planned for Phase 5.

Meshing, solver runs and margins per load case. Output: `margins` artifact.

## Connectors (OD-3, decided 2026-11-24: "all solver")

| Folder | Solver | Role | Source | Note |
|---|---|---|---|---|
| `calculix/` | CalculiX | Default structural solver | plan Phase 5 task 3 | GPL: separate process or container (plan §9) |
| `code_aster/` | Code_Aster | Cases CalculiX cannot cover | plan Phase 5 task 3 | GPL: separate process or container (plan §9) |
| `fenicsx/` | FEniCSx | Custom physics | plan Phase 5 task 3 | |
| `ansys_import/` | Ansys result import | Import results from Ansys runs | deck slides 27, 65, 90 | Needs an Ansys licence (deck slide 90). Not in the plan; added by OD-3 |

Every connector reproduces benchmark problems before it is trusted (plan Phase 5 task 6, exit: within 3 % of reference).

Planned stack: Gmsh / Netgen, CalculiX, Code_Aster, FEniCSx, meshio, PyVista (plan §4.2). The deck also names FreeCAD FEM for CalculiX runs (deck slides 20, 65; plan-vs-deck L4).

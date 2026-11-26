# Block 5: OpenCAD Adapters

**Status: first slice built (2026-11-26).** Package `edp_b5_opencad`.

Runs the generated script, checks the solid, verifies it against the drawing and exports it (plan Phase 4 OpenCAD tasks 1 to 3). Output: `step` artifact; STL is also written to the Fabric.

| Built | Detail |
|---|---|
| Sandbox | `runner.py` runs the script in its own Python process (`-I`) with a time limit (`EDP_SANDBOX_TIMEOUT_S`, OD-58). It is not a container without network (OD-21) |
| Validity | `BRepCheck_Analyzer`, exactly one solid, volume > 0. Failure gives `INVALID_SOLID` |
| Dimensional check | Bounding box against length, width and thickness. Three probes per hole: the bore centre is empty, a point just inside the drawn diameter is empty, and the material just outside is solid. Failure gives `DIMENSION_MISMATCH` with the drawing locator |
| Export | STEP and STL through the CadQuery exporters |

Not built:
- watertightness and minimum-thickness checks;
- glTF/GLB export and thumbnails;
- the FreeCAD fallback;
- the CadAdapter protocol of deck slide 47.

Planned stack (plan §4.2): OCP (OpenCascade), BRepCheck_Analyzer, trimesh, CadQuery exporters, FreeCAD headless fallback.

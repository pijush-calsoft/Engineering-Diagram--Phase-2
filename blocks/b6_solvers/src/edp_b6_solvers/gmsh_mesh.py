"""Mesh a STEP solid with Gmsh. Runs in its own Python process, never imported by the platform.

Gmsh is GPL, so it runs as a separate process (plan §9); this file imports only ``gmsh`` and
the standard library. Usage: ``python -I gmsh_mesh.py <job.json>``. The job holds ``step``,
``out``, ``size_max`` and ``size_min`` (mm). Output JSON:

- ``nodes``: {id: [x, y, z]}
- ``elements``: [[id, n1..n10]] second-order tetrahedra, in CalculiX C3D10 node order
- ``sets``: node ids on cylindrical faces (``bores``) and on the top plane face (``top``)
- ``quality``: element count and the minimum and mean scaled Jacobian (mesh check, plan Phase 5)
"""

import json
import sys

import gmsh

# Gmsh tetra10 -> CalculiX/Abaqus C3D10: Gmsh numbers the last two mid-edge nodes (2-3, 1-3)
# the other way round from Abaqus (1-3, 2-3).
TET10_ORDER = [0, 1, 2, 3, 4, 5, 6, 7, 9, 8]


def main(job_path: str) -> int:
    job = json.loads(open(job_path, encoding="utf-8").read())
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    try:
        gmsh.model.occ.importShapes(job["step"])
        gmsh.model.occ.synchronize()
        gmsh.option.setNumber("Mesh.MeshSizeMax", job["size_max"])
        gmsh.option.setNumber("Mesh.MeshSizeMin", job["size_min"])
        gmsh.option.setNumber("Mesh.ElementOrder", 2)
        gmsh.model.mesh.generate(3)

        zmax = max(gmsh.model.getBoundingBox(d, t)[5] for d, t in gmsh.model.getEntities(3))
        bores: set[int] = set()
        top: set[int] = set()
        for dim, tag in gmsh.model.getEntities(2):
            kind = gmsh.model.getType(dim, tag)
            nodes = gmsh.model.mesh.getNodes(dim, tag, includeBoundary=True)[0]
            if kind == "Cylinder":
                bores.update(int(n) for n in nodes)
            elif kind == "Plane":
                box = gmsh.model.getBoundingBox(dim, tag)
                if abs(box[2] - zmax) < 1e-6 and abs(box[5] - zmax) < 1e-6:
                    top.update(int(n) for n in nodes)

        tags, coords, _ = gmsh.model.mesh.getNodes()
        nodes_out = {
            int(t): [coords[3 * i], coords[3 * i + 1], coords[3 * i + 2]] for i, t in enumerate(tags)
        }
        elements = []
        etypes, etags, enodes = gmsh.model.mesh.getElements(3)
        for et, tags_e, nodes_e in zip(etypes, etags, enodes, strict=True):
            if et != 11:  # 10-node tetrahedron
                raise RuntimeError(f"unexpected volume element type {et}")
            for i, t in enumerate(tags_e):
                conn = [int(n) for n in nodes_e[10 * i : 10 * i + 10]]
                elements.append([int(t)] + [conn[k] for k in TET10_ORDER])
        qual = gmsh.model.mesh.getElementQualities([int(t) for t in etags[0]], "minSJ") if len(etags) else []
        out = {
            "nodes": nodes_out,
            "elements": elements,
            "sets": {"bores": sorted(bores), "top": sorted(top)},
            "quality": {
                "elements": len(elements),
                "min_scaled_jacobian": float(min(qual)) if len(qual) else None,
                "mean_scaled_jacobian": float(sum(qual) / len(qual)) if len(qual) else None,
            },
        }
        with open(job["out"], "w", encoding="utf-8") as f:
            json.dump(out, f)
    finally:
        gmsh.finalize()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))

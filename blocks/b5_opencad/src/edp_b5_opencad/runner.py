"""Sandbox runner: executes one generated CadQuery script in its own process.

Run as ``python -I runner.py <workdir>``. The work folder holds ``script.py`` and
``checks.json``; the runner writes ``model.step``, ``model.stl`` and ``report.json``.
It is a separate process so a broken or hostile script cannot touch the platform process
(plan Phase 6 hardening: "sandbox escape in generated code"; deck slide 47 "Sandbox runner").
This file imports only cadquery and OCP, never platform code.
"""

import json
import sys
import traceback
from pathlib import Path


def main(workdir: Path) -> int:
    report: dict = {"ok": False}
    try:
        import cadquery as cq
        from OCP.BRepCheck import BRepCheck_Analyzer
        from OCP.BRepClass3d import BRepClass3d_SolidClassifier
        from OCP.BRepGProp import BRepGProp
        from OCP.gp import gp_Pnt
        from OCP.GProp import GProp_GProps
        from OCP.TopAbs import TopAbs_IN, TopAbs_OUT

        namespace: dict = {}
        exec(compile((workdir / "script.py").read_text(encoding="utf-8"), "script.py", "exec"), namespace)
        result = namespace.get("result")
        if not isinstance(result, cq.Workplane):
            raise TypeError("the script must assign a CadQuery Workplane to 'result'")
        shape = result.val()
        if not isinstance(shape, cq.Shape):
            raise TypeError("the script's result holds no solid shape")
        solids = result.solids().vals()
        valid = bool(BRepCheck_Analyzer(shape.wrapped).IsValid())
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(shape.wrapped, props)
        bb = shape.BoundingBox()
        probes = []
        for probe in json.loads((workdir / "checks.json").read_text(encoding="utf-8"))["probes"]:
            classifier = BRepClass3d_SolidClassifier(shape.wrapped, gp_Pnt(*probe["point"]), 1e-6)
            state = classifier.State()
            inside = state == TopAbs_IN
            probes.append(
                {
                    **probe,
                    "inside": inside,
                    "ok": inside == probe["expect_inside"] and state in (TopAbs_IN, TopAbs_OUT),
                }
            )
        cq.exporters.export(result, str(workdir / "model.step"))
        cq.exporters.export(result, str(workdir / "model.stl"))
        report = {
            "ok": True,
            "valid": valid,
            "solids": len(solids),
            "volume": props.Mass(),
            "bbox": [bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax],
            "probes": probes,
        }
    except Exception as exc:  # reported back to block 5 as a structured error
        report = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()}
    (workdir / "report.json").write_text(json.dumps(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1])))

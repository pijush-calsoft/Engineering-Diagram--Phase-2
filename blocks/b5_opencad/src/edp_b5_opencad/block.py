"""Block 5, OpenCAD Adapters, as a plug-in (plan §3, Phase 4): ``cad_script`` in, ``step`` out.

1. Runs the script in a separate process with a time limit (``runner.py``; plan Phase 4
   OpenCAD task 1, deck slide 47 "Sandbox runner").
2. Validity: ``BRepCheck_Analyzer``, exactly one solid, volume > 0 (plan Phase 4 OpenCAD task 1).
3. Dimensional verification against the parameter table, which carries the drawing values:
   the bounding box against length, width and thickness, and two probe points per hole (void
   at the centre, material just outside the bore). Plan Phase 4 OpenCAD task 2.
4. Exports STEP and STL into the Data Fabric (plan Phase 4 OpenCAD task 3; glTF not yet).

Limits: the sandbox is a separate process with a time limit, not a container without network
(deck slide 47 "Container, no network"): containers are out of the POC (OD-21). The time limit
is ``EDP_SANDBOX_TIMEOUT_S``; unset, it is 120 s, the value shown on deck slide 79 (AD-1).
The plan leaves sandbox limits open (TBD-AC-4).
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from edp_contracts import Artifact, BlockRequest, BlockResult, Flag, SourceLocator
from edp_contracts.artifacts.cad_script import CadScript
from edp_kit import ArtifactStore, pass_through, skip_reason

RUNNER = Path(__file__).with_name("runner.py")
DEFAULT_TIMEOUT_S = 120.0  # deck slide 79, AD-1 mock-up "Timeout and retry: 120 s"
SIZE_TOL_MM = 1e-3  # generated geometry is exact; this only absorbs floating-point noise
PROBE_OFFSET_MM = 0.25  # how far outside a bore the "material" probe sits


def timeout_s() -> float:
    value = os.environ.get("EDP_SANDBOX_TIMEOUT_S", "").strip()
    return float(value) if value else DEFAULT_TIMEOUT_S


def probes_for(params: dict[str, float]) -> list[dict[str, Any]]:
    """Probe points for every hole ``<id>_x``, ``<id>_y``, ``<id>_diameter`` in the table."""
    if not {"length", "width", "thickness"} <= set(params):
        return []
    cx, cy, mid = params["length"] / 2, params["width"] / 2, params["thickness"] / 2
    out = []
    for name in sorted(params):
        if not name.endswith("_diameter"):
            continue
        hid = name[: -len("_diameter")]
        if f"{hid}_x" not in params or f"{hid}_y" not in params:
            continue
        x, y, r = params[f"{hid}_x"], params[f"{hid}_y"], params[name] / 2
        dx, dy = cx - x, cy - y  # step toward the plate centre so the probe stays in the plate
        norm = (dx * dx + dy * dy) ** 0.5 or 1.0
        ux, uy = dx / norm, dy / norm
        rim = (x + ux * (r - PROBE_OFFSET_MM), y + uy * (r - PROBE_OFFSET_MM), mid)
        wall = (x + ux * (r + PROBE_OFFSET_MM), y + uy * (r + PROBE_OFFSET_MM), mid)
        out.append({"feature": hid, "what": "bore is empty", "point": [x, y, mid], "expect_inside": False})
        out.append(
            {
                "feature": hid,
                "what": "bore reaches its drawn diameter",
                "point": list(rim),
                "expect_inside": False,
            }
        )
        out.append(
            {"feature": hid, "what": "material outside the bore", "point": list(wall), "expect_inside": True}
        )
    return out


class OpenCadAdapters:
    name = "b5_opencad"
    version = "0.1.0"
    accepts = {"cad_script"}
    produces = {"step"}

    def __init__(self, store: ArtifactStore | None = None) -> None:
        self._store = store

    @property
    def store(self) -> ArtifactStore:
        if self._store is None:
            from edp_fabric import FabricStore  # entry-point loading: local Fabric (ADR-0008)

            data_dir = os.environ.get("EDP_DATA_DIR")
            if not data_dir:
                raise RuntimeError(
                    "OpenCadAdapters needs a store, or EDP_DATA_DIR set to the local data folder"
                )
            self._store = FabricStore(Path(data_dir) / "fabric")
        return self._store

    def run(self, req: BlockRequest) -> BlockResult:
        reason = skip_reason(req)
        if reason:
            return pass_through(self.name, self.produces, req, reason)
        outputs: list[Artifact] = []
        flags: list[Flag] = []
        metrics: dict[str, object] = {}
        failed = False
        for i, art in enumerate(req.inputs):
            script = CadScript.model_validate_json(self.store.read(art.uri))
            params = {p.name: float(p.value) for p in script.parameters if isinstance(p.value, (int, float))}
            sources = {p.name: p.source for p in script.parameters}
            started = time.perf_counter()
            report, step, stl = self._execute(script.code, probes_for(params))
            seconds = round(time.perf_counter() - started, 3)
            if not report.get("ok"):
                failed = True
                flags.append(Flag(code="SCRIPT_ERROR", message=str(report.get("error")), severity="block"))
                metrics[art.uri] = {"seconds": seconds, "error": report.get("error")}
                continue
            checks, check_flags = self._verify(report, params, sources)
            flags += check_flags
            step_uri = self.store.write(req.run_id, self.name, f"model-{i}.step", step)
            stl_uri = self.store.write(req.run_id, self.name, f"model-{i}.stl", stl)
            outputs.append(Artifact(kind="step", uri=step_uri, schema_version="file", sources=art.sources))
            passed = sum(1 for c in checks if c["ok"])
            metrics[art.uri] = {
                "seconds": seconds,
                "valid_solid": report["valid"] and report["solids"] == 1 and report["volume"] > 0,
                "volume_mm3": report["volume"],
                "bbox_mm": report["bbox"],
                "checks": checks,
                "features_within_tolerance": passed / len(checks) if checks else None,
                "stl_uri": stl_uri,
                "script_uri": art.uri,
            }
        if failed:
            status = "failed"
        elif any(f.severity in ("review", "block") for f in flags):
            status = "needs_review"
        else:
            status = "ok"
        return BlockResult(run_id=req.run_id, status=status, outputs=outputs, flags=flags, metrics=metrics)

    def _execute(self, code: str, probes: list[dict[str, Any]]) -> tuple[dict[str, Any], bytes, bytes]:
        with tempfile.TemporaryDirectory(prefix="edp-sandbox-") as tmp:
            work = Path(tmp)
            (work / "script.py").write_text(code, encoding="utf-8")
            (work / "checks.json").write_text(json.dumps({"probes": probes}), encoding="utf-8")
            try:
                subprocess.run(
                    [sys.executable, "-I", str(RUNNER), str(work)],
                    cwd=work,
                    timeout=timeout_s(),
                    capture_output=True,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return {"ok": False, "error": f"script ran longer than {timeout_s():g} s"}, b"", b""
            report_path = work / "report.json"
            if not report_path.exists():
                return {"ok": False, "error": "sandbox process ended without a report"}, b"", b""
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if not report.get("ok"):
                return report, b"", b""
            return report, (work / "model.step").read_bytes(), (work / "model.stl").read_bytes()

    @staticmethod
    def _verify(
        report: dict[str, Any], params: dict[str, float], sources: dict[str, SourceLocator]
    ) -> tuple[list[dict[str, Any]], list[Flag]]:
        checks: list[dict[str, Any]] = []
        flags: list[Flag] = []
        if not report["valid"] or report["solids"] != 1 or report["volume"] <= 0:
            flags.append(
                Flag(
                    code="INVALID_SOLID",
                    message=(
                        f"valid={report['valid']}, solids={report['solids']}, volume={report['volume']:g}"
                    ),
                    severity="review",
                )
            )
        x0, y0, z0, x1, y1, z1 = report["bbox"]
        for name, measured in (("length", x1 - x0), ("width", y1 - y0), ("thickness", z1 - z0)):
            if name not in params:
                continue
            ok = abs(measured - params[name]) <= SIZE_TOL_MM
            checks.append({"feature": name, "expected": params[name], "measured": measured, "ok": ok})
            if not ok:
                flags.append(
                    Flag(
                        code="DIMENSION_MISMATCH",
                        target=sources.get(name),
                        message=f"{name}: model {measured:g} mm, drawing {params[name]:g} mm",
                    )
                )
        for p in report["probes"]:
            checks.append({"feature": p["feature"], "check": p["what"], "ok": p["ok"]})
            if not p["ok"]:
                flags.append(
                    Flag(
                        code="DIMENSION_MISMATCH",
                        target=sources.get(f"{p['feature']}_diameter"),
                        message=f"{p['feature']}: {p['what']} failed at {p['point']}",
                    )
                )
        return checks, flags

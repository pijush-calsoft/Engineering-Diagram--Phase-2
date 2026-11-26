"""Block 6, Solver Connectors, as a plug-in (plan §3, Phase 5): ``step`` + ``design_graph`` in,
``margins`` out.

For each load case in the domain pack that applies to the part family:

1. Mesh the STEP model with Gmsh (second-order tetrahedra) and record mesh quality.
2. Build the boundary conditions from the load case. ``base_plate_uplift``: the anchor-bolt
   bores are fixed and the column's tension is spread over the top-face nodes inside the column
   footprint, centred on the plate.
3. Run CalculiX and read the maximum von Mises stress and displacement.
4. Margin = allowable / computed, with allowable = f_y / gamma_M0 from the material card
   (``Margin.margin``; deck slide 53: "margin is capacity over demand; 1.0 means failure").

Every margin carries the governing location on the model, the solver run id, the load-case row
(file hash and case id) and the model version (plan Phase 5 exit criterion).

Modelling limits, stated in each result: linear elastic, small displacement; bolts modelled as
fixed bores (no bolt stiffness, no washer contact, no grout); load as equal nodal forces over the
footprint. The peak stress at a fixed bore edge is mesh-sensitive.
"""

import hashlib
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from edp_b6_solvers import calculix, packs
from edp_contracts import Artifact, BlockRequest, BlockResult, Flag, SourceLocator
from edp_contracts.artifacts.design_graph import DesignGraph
from edp_contracts.artifacts.margins import SCHEMA_VERSION, Margin, Margins
from edp_contracts.artifacts.solver_runs import SCHEMA_VERSION as RUNS_SCHEMA_VERSION
from edp_contracts.artifacts.solver_runs import MaterialUsed, MeshInfo, SolverRun, SolverRuns
from edp_kit import ArtifactStore, OverrideError, overrides, pass_through, skip_reason

ASSUMPTIONS = [
    "linear elastic, small displacement",
    "anchor bolt bores fixed (no bolt stiffness, washer contact or grout)",
    "column tension as equal nodal forces over the footprint on the top face",
    "peak stress at a fixed bore edge is mesh-sensitive",
]

DEFAULT_TIMEOUT_S = 1800.0  # deck slide 48 CalculiX adapter spec example: "timeout_s: 1800"
FAMILY_BY_PACK = {"construction": "base_plate"}


def timeout_s() -> float:
    value = os.environ.get("EDP_SOLVER_TIMEOUT_S", "").strip()
    return float(value) if value else DEFAULT_TIMEOUT_S


def _outline(graph: DesignGraph) -> dict[str, float]:
    out: dict[str, float] = {}
    for n in graph.nodes:
        role = n.attributes.get("role")
        if n.kind == "parameter" and role and n.attributes.get("value_mm") is not None:
            out.setdefault(str(role), float(n.attributes["value_mm"]))
    return out


def _hole_diameters(graph: DesignGraph) -> list[float]:
    return [
        float(n.attributes["value_mm"])
        for n in graph.nodes
        if n.kind == "parameter"
        and n.id.startswith("hole")
        and n.id.endswith(".diameter")
        and n.attributes.get("value_mm") is not None
    ]


def mesh_sizes(thickness: float, holes: list[float]) -> tuple[float, float]:
    """Element size: half the smaller of the thickness and the smallest hole; a quarter of that at
    the finest. Starting values, not plan values (OD-57); a convergence check is still open."""
    base = min([thickness, *holes]) / 2
    return base, base / 4


class SolverConnectors:
    name = "b6_solvers"
    version = "0.1.0"
    accepts = {"step", "design_graph"}
    produces = {"margins", "solver_runs"}

    def __init__(self, store: ArtifactStore | None = None) -> None:
        self._store = store

    @property
    def store(self) -> ArtifactStore:
        if self._store is None:
            from edp_fabric import FabricStore  # entry-point loading: local Fabric (ADR-0008)

            data_dir = os.environ.get("EDP_DATA_DIR")
            if not data_dir:
                raise RuntimeError(
                    "SolverConnectors needs a store, or EDP_DATA_DIR set to the local data folder"
                )
            self._store = FabricStore(Path(data_dir) / "fabric")
        return self._store

    def run(self, req: BlockRequest) -> BlockResult:
        reason = skip_reason(req)
        if reason:
            return pass_through(self.name, self.produces, req, reason)
        pack_name = str(req.params["domain_pack"])
        steps = [a for a in req.inputs if a.kind == "step"]
        graphs = [a for a in req.inputs if a.kind == "design_graph"]
        if not steps or not graphs:
            return self._fail(req, "MISSING_INPUT", "block 6 needs a STEP model and its design graph")
        try:
            materials = packs.load(pack_name, "materials.json")
            cases = packs.load(pack_name, "load_cases.json")
        except packs.PackError as exc:
            return self._fail(req, "DOMAIN_PACK_MISSING", str(exc))
        graph = DesignGraph.model_validate_json(self.store.read(graphs[0].uri))
        outline = _outline(graph)
        try:
            # The STEP was built with the run's overrides (block 4); size the mesh, choose the
            # yield band and place the loads with the same values.
            outline.update(overrides(req))
        except OverrideError as exc:
            return self._fail(req, "BAD_OVERRIDE", str(exc))
        grade = next((str(n.attributes.get("name")) for n in graph.nodes if n.kind == "material"), None)
        if grade is None or "thickness" not in outline:
            return self._fail(req, "MISSING_INPUT", "design graph needs a material and the plate thickness")
        try:
            card = packs.material(materials, grade, outline["thickness"])
        except packs.PackError as exc:
            return self._fail(req, "MATERIAL_UNKNOWN", str(exc))

        family = FAMILY_BY_PACK.get(pack_name)
        wanted = req.params.get("load_cases")
        selected = [
            lc
            for lc in cases.data["load_cases"]
            if family in lc.get("applies_to", []) and (not wanted or lc["id"] in wanted)
        ]
        if not selected:
            return self._fail(req, "NO_LOAD_CASE", f"no load case in pack {pack_name!r} applies to {family}")

        step_art = steps[0]
        step_bytes = self.store.read(step_art.uri)
        model_version = f"{step_art.uri}#sha256={hashlib.sha256(step_bytes).hexdigest()[:16]}"
        flags: list[Flag] = []
        margins: list[Margin] = []
        runs: list[SolverRun] = []
        size_max, size_min = mesh_sizes(outline["thickness"], _hole_diameters(graph))
        with tempfile.TemporaryDirectory(prefix="edp-b6-") as tmp:
            step_file = Path(tmp) / "model.step"
            step_file.write_bytes(step_bytes)
            started = time.perf_counter()
            try:
                mesh = calculix.mesh_step(step_file, size_max, size_min, timeout_s())
            except calculix.SolverUnavailableError as exc:
                return self._fail(req, exc.code, str(exc))
            mesh_seconds = time.perf_counter() - started
            for lc in selected:
                if lc.get("illustrative"):
                    flags.append(
                        Flag(
                            code="ILLUSTRATIVE_LOAD",
                            message=f"{lc['id']} is an illustrative load, not a design value (OD-56)",
                            target=cases.locator(lc["id"]),
                            severity="info",
                        )
                    )
                if lc["kind"] != "base_plate_uplift":
                    flags.append(Flag(code="LOAD_CASE_UNSUPPORTED", message=f"{lc['id']}: kind {lc['kind']}"))
                    continue
                fixed, loads, loaded = self._uplift(mesh, outline, lc)
                if not fixed or not loaded:
                    flags.append(
                        Flag(
                            code="BOUNDARY_CONDITIONS",
                            message=f"{lc['id']}: no bore or footprint nodes found",
                        )
                    )
                    continue
                run_id = f"ccx-{uuid.uuid4().hex[:10]}"
                t0 = time.perf_counter()
                result = calculix.run_ccx(
                    calculix.write_inp(mesh, card.E, card.nu, fixed, loads), mesh, timeout_s()
                )
                allowable = card.fy / card.gamma_M0
                where = SourceLocator(
                    file_id=hashlib.sha256(step_bytes).hexdigest(),
                    version=model_version,
                    handle=f"element {result.max_element}",
                    bbox=(result.max_point[0], result.max_point[1], result.max_point[0], result.max_point[1]),
                    confidence=1.0,
                )
                margins.append(
                    Margin(
                        load_case_id=lc["id"],
                        quantity="stress",
                        allowable=allowable,
                        computed=result.max_von_mises,
                        governing_location=where,
                        solver_run_id=run_id,
                        load_case_row=cases.locator(lc["id"]),
                        model_version=model_version,
                    )
                )
                runs.append(
                    SolverRun(
                        solver_run_id=run_id,
                        solver="calculix",
                        solver_version=result.extra.get("version"),
                        load_case_id=lc["id"],
                        load_case_row=cases.locator(lc["id"]),
                        illustrative_load=bool(lc.get("illustrative")),
                        model_version=model_version,
                        material=MaterialUsed(
                            grade=card.grade,
                            fy_MPa=card.fy,
                            gamma_M0=card.gamma_M0,
                            E_MPa=card.E,
                            nu=card.nu,
                            row=card.row,
                        ),
                        total_force_N=float(lc["axial_tension_kN"]) * 1000.0,
                        fixed_nodes=len(fixed),
                        loaded_nodes=loaded,
                        max_von_mises_MPa=result.max_von_mises,
                        max_point_mm=result.max_point,
                        max_displacement_mm=result.max_displacement,
                        allowable_MPa=allowable,
                        seconds=round(time.perf_counter() - t0, 2),
                        assumptions=ASSUMPTIONS,
                    )
                )
        doc = Margins(margins=margins)
        uri = self.store.write(req.run_id, self.name, "margins.json", doc.model_dump_json().encode())
        run_record = SolverRuns(
            domain_pack=pack_name,
            materials_sha256=materials.sha256,
            load_cases_sha256=cases.sha256,
            mesh=MeshInfo(
                elements=int(mesh.quality["elements"]),
                nodes=len(mesh.nodes),
                element_type="C3D10",
                size_max_mm=size_max,
                size_min_mm=size_min,
                min_scaled_jacobian=mesh.quality.get("min_scaled_jacobian"),
                mean_scaled_jacobian=mesh.quality.get("mean_scaled_jacobian"),
            ),
            runs=runs,
        )
        runs_uri = self.store.write(
            req.run_id, self.name, "solver_runs.json", run_record.model_dump_json().encode()
        )
        for m in margins:
            if m.margin < 1.0:
                flags.append(
                    Flag(
                        code="MARGIN_BELOW_ONE",
                        message=f"{m.load_case_id}: margin {m.margin:.2f} < 1.0",
                        target=m.governing_location,
                    )
                )
        metrics: dict[str, Any] = {
            "thickness_mm": outline["thickness"],
            "overrides": overrides(req),
            "mesh_seconds": round(mesh_seconds, 2),
            "runs": [
                {
                    "load_case": r.load_case_id,
                    "seconds": r.seconds,
                    "margin": r.allowable_MPa / r.max_von_mises_MPa,
                }
                for r in runs
            ],
        }
        sources = [*step_art.sources]
        status = "needs_review" if any(f.severity in ("review", "block") for f in flags) else "ok"
        outputs: list[Artifact] = []
        if margins:
            outputs = [
                Artifact(kind="margins", uri=uri, schema_version=SCHEMA_VERSION, sources=sources),
                Artifact(
                    kind="solver_runs", uri=runs_uri, schema_version=RUNS_SCHEMA_VERSION, sources=sources
                ),
            ]
        else:
            status = "failed"
        return BlockResult(run_id=req.run_id, status=status, outputs=outputs, flags=flags, metrics=metrics)

    @staticmethod
    def _uplift(
        mesh: calculix.Mesh, outline: dict[str, float], lc: dict[str, Any]
    ) -> tuple[list[int], dict[int, tuple[float, float, float]], int]:
        fixed = sorted(mesh.sets.get("bores", []))
        bx, by = (float(v) for v in lc["column_footprint_mm"])
        cx, cy = outline.get("length", 0.0) / 2, outline.get("width", 0.0) / 2
        top = [
            n
            for n in mesh.sets.get("top", [])
            if abs(mesh.nodes[n][0] - cx) <= bx / 2 and abs(mesh.nodes[n][1] - cy) <= by / 2
        ]
        total = float(lc["axial_tension_kN"]) * 1000.0
        loads = {n: (0.0, 0.0, total / len(top)) for n in top} if top else {}
        return fixed, loads, len(top)

    def _fail(self, req: BlockRequest, code: str, message: str) -> BlockResult:
        return BlockResult(
            run_id=req.run_id,
            status="failed",
            outputs=[],
            flags=[Flag(code=code, message=message, severity="block")],
        )

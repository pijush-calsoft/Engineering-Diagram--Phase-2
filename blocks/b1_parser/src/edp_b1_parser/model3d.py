"""3D inputs: STEP and IGES with OCP, STL with trimesh (plan Phase 2, "Approach by input").

- **STEP, IGES**: "OCP readers, topology walk (faces, edges, holes), STEP entity ids as
  locators". Per solid: bounding box, volume, face count by surface type, edge count and
  holes. A hole is a set of cylindrical faces around one axis that lies outside the material
  (a bore, not a boss) and that together go all the way round (360 degrees; a bore is often
  two half faces). Partial cylinders, such as the rounded ends of a slot, are not holes.
  OCP reads lengths in mm.
- **STL**: "trimesh: watertightness, bounding box, feature hints; flag as lossy input". The
  hint is the through-hole count of a closed mesh (its genus). STL has no units, so the
  drawing is flagged as unit-less rather than given a unit.

OCCT is LGPL-2.1 with an exception (plan §4.2) and is used as an unmodified library (plan §9).
"""

import io
import math
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from edp_contracts import Flag, SourceLocator
from edp_contracts.artifacts.geometry import Geometry, Hole3D, Solid

AXIS_ROUND = 6  # decimals used to group faces of one bore (same axis and radius)
FULL_TURN = 2 * math.pi - 1e-6  # faces around one axis must go all the way round to be a hole


@contextmanager
def _temp_file(data: bytes, suffix: str) -> Iterator[str]:
    fd, path = tempfile.mkstemp(prefix="edp-3d-", suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        yield path
    finally:
        os.unlink(path)


def _quiet_ocp() -> None:
    """Stop OCCT printing transfer statistics to the console."""
    from OCP.Message import Message, Message_Gravity

    printers = Message.DefaultMessenger_s().Printers()
    for i in range(1, printers.Length() + 1):
        printers.Value(i).SetTraceLevel(Message_Gravity.Message_Fail)


def _unique(shape: Any, kind: Any, hasher: Any, explorer: Any) -> int:
    """Count distinct sub-shapes: an explorer visits a shared edge once per adjacent face."""
    buckets: dict[int, list[Any]] = {}
    ex = explorer(shape, kind)
    while ex.More():
        sub = ex.Current()
        same = buckets.setdefault(hasher(sub), [])
        if not any(sub.IsSame(x) for x in same):
            same.append(sub)
        ex.Next()
    return sum(len(v) for v in buckets.values())


def parse_brep(
    data: bytes, kind: str, file_id: str, version: str
) -> tuple[Geometry, list[Flag], dict[str, Any]]:
    """STEP (``kind="step"``) or IGES (``kind="iges"``) to a geometry artifact with solids."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.BRepGProp import BRepGProp
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.gp import gp_Pnt
    from OCP.GProp import GProp_GProps
    from OCP.IFSelect import IFSelect_ReturnStatus
    from OCP.IGESControl import IGESControl_Reader
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_OUT, TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    from OCP.TopTools import TopTools_ShapeMapHasher

    _quiet_ocp()
    flags: list[Flag] = []
    reader = STEPControl_Reader() if kind == "step" else IGESControl_Reader()
    with _temp_file(data, ".step" if kind == "step" else ".igs") as path:
        status = reader.ReadFile(path)
    if status != IFSelect_ReturnStatus.IFSelect_RetDone:
        raise ValueError(f"OCP could not read the {kind.upper()} file (status {status})")
    reader.TransferRoots()
    shape = reader.OneShape()
    model = reader.WS().Model()
    transfer = reader.WS().TransferReader()
    numbers = {model.Value(i): i for i in range(1, model.NbEntities() + 1)}  # entity object -> number

    def handle(sub: Any) -> str | None:
        ent = transfer.EntityFromShapeResult(sub, 1)
        n = numbers.get(ent) if ent is not None else None
        if n is None:
            return None
        return f"#{n}" if kind == "step" else f"DE{2 * n - 1}"  # IGES directory entry number

    def loc(h: str | None) -> SourceLocator:
        return SourceLocator(file_id=file_id, version=version, view="3d", handle=h, confidence=1.0)

    solids = []
    exp = TopExp_Explorer(shape, TopAbs_SOLID)
    bodies = []
    while exp.More():
        bodies.append(TopoDS.Solid(exp.Current()))
        exp.Next()
    if not bodies:
        flags.append(
            Flag(code="NO_SOLID", severity="review", message=f"the {kind.upper()} file has no closed solid")
        )
        bodies = [shape]
    for body in bodies:
        box = Bnd_Box()
        BRepBndLib.Add_s(body, box)
        lo, hi = box.CornerMin(), box.CornerMax()
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(body, props)
        edges = _unique(body, TopAbs_EDGE, TopTools_ShapeMapHasher(), TopExp_Explorer)
        faces: dict[str, int] = {}
        bores: dict[tuple, dict[str, Any]] = {}
        fx = TopExp_Explorer(body, TopAbs_FACE)
        while fx.More():
            face = TopoDS.Face(fx.Current())
            surf = BRepAdaptor_Surface(face)
            name = str(surf.GetType()).split("_")[-1].lower()
            faces[name] = faces.get(name, 0) + 1
            if surf.GetType() == GeomAbs_Cylinder:
                cyl = surf.Cylinder()
                ax, r = cyl.Axis(), cyl.Radius()
                o, d = ax.Location(), ax.Direction()
                v = (surf.FirstVParameter() + surf.LastVParameter()) / 2
                probe = gp_Pnt(o.X() + d.X() * v, o.Y() + d.Y() * v, o.Z() + d.Z() * v)
                if BRepClass3d_SolidClassifier(body, probe, 1e-7).State() == TopAbs_OUT:
                    direction = (d.X(), d.Y(), d.Z())
                    if max(direction, key=abs) < 0:  # one sign per axis line
                        direction = tuple(-c for c in direction)
                    t = o.X() * direction[0] + o.Y() * direction[1] + o.Z() * direction[2]
                    foot = (o.X() - t * direction[0], o.Y() - t * direction[1], o.Z() - t * direction[2])
                    key = (round(r, AXIS_ROUND), *(round(c, AXIS_ROUND) for c in (*direction, *foot)))
                    bore = bores.setdefault(
                        key,
                        {"r": r, "origin": (o.X(), o.Y(), o.Z()), "dir": direction, "locs": [], "sweep": 0.0},
                    )
                    bore["locs"].append(loc(handle(face)))
                    bore["sweep"] += surf.LastUParameter() - surf.FirstUParameter()
            fx.Next()
        holes = [
            Hole3D(diameter=2 * b["r"], axis_origin=b["origin"], axis_direction=b["dir"], locators=b["locs"])
            for b in bores.values()
            if b["sweep"] >= FULL_TURN
        ]
        solids.append(
            Solid(
                locator=loc(handle(body)),
                bbox=(lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()),
                volume=props.Mass(),
                faces=faces,
                edges=edges,
                holes=holes,
            )
        )
    geometry = Geometry(views=["3d"], units="mm", solids=solids)
    metrics = {
        "solids": len(solids),
        "holes": sum(len(s.holes) for s in solids),
        "faces": sum(sum(s.faces.values()) for s in solids),
    }
    return geometry, flags, metrics


def _components(edges: Any, n_vertices: int) -> int:
    """Connected bodies of a mesh (union-find over its edges; no graph library needed)."""
    parent = list(range(n_vertices))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in edges:
        ra, rb = find(int(a)), find(int(b))
        if ra != rb:
            parent[ra] = rb
    used = {int(v) for e in edges for v in e}
    return len({find(v) for v in used})


def parse_stl(data: bytes, file_id: str, version: str) -> tuple[Geometry, list[Flag], dict[str, Any]]:
    import trimesh

    mesh: Any = trimesh.load(io.BytesIO(data), file_type="stl", force="mesh")  # a trimesh.Trimesh
    flags = [
        Flag(
            code="LOSSY_INPUT",
            severity="info",
            message="STL is a triangle mesh: exact dimensions, tolerances and features are not available",
        ),
        Flag(code="UNIT_MISMATCH", message="[UNITS_UNKNOWN] STL files carry no units"),
    ]
    watertight = bool(mesh.is_watertight)
    if not watertight:
        flags.append(
            Flag(
                code="MESH_NOT_WATERTIGHT",
                severity="review",
                message="the mesh is not closed: volume and hole hints are not available",
            )
        )
    lo, hi = mesh.bounds
    bodies = _components(mesh.edges_unique, len(mesh.vertices)) if watertight else 0
    # Closed surfaces: Euler number = sum over bodies of (2 - 2 genus).
    genus = max(0, round((2 * bodies - int(mesh.euler_number)) / 2)) if watertight else None
    solid = Solid(
        locator=SourceLocator(file_id=file_id, version=version, view="3d", handle="mesh", confidence=1.0),
        bbox=(float(lo[0]), float(lo[1]), float(lo[2]), float(hi[0]), float(hi[1]), float(hi[2])),
        volume=float(mesh.volume) if watertight else None,
        faces={"triangle": int(len(mesh.faces))},
        watertight=watertight,
        through_holes_hint=genus,
        lossy=True,
    )
    geometry = Geometry(views=["3d"], units=None, solids=[solid])
    metrics = {
        "triangles": int(len(mesh.faces)),
        "watertight": watertight,
        "bodies": bodies or None,
        "extent": [float(v) for v in (hi - lo)],
        "diagonal": float(math.dist(lo, hi)),
    }
    return geometry, flags, metrics

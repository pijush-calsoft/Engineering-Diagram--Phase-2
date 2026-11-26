"""Triangle meshes of 3D inputs, for the console's 3D viewer (plan Phase 6: "3D viewer").

Display only: nothing here feeds an engineering value. STEP and IGES are tessellated with OCP
(``BRepMesh_IncrementalMesh``); each face keeps its entity id (``#n`` for STEP, ``DE<n>`` for
IGES), so the viewer can highlight the faces a locator points at. STL triangles are used as
they are. The tessellation tolerance is relative to the part size and only affects how smooth
the picture is (``LINEAR_DEFLECTION``, ``ANGULAR_DEFLECTION_RAD``).
"""

import io

from pydantic import BaseModel

from edp_b1_parser.model3d import _quiet_ocp, _temp_file

LINEAR_DEFLECTION = 0.001  # fraction of the bounding-box diagonal
ANGULAR_DEFLECTION_RAD = 0.3


class FaceRange(BaseModel):
    handle: str | None  # entity id of the face, as in the geometry artifact's locators
    start: int  # first triangle
    count: int  # number of triangles


class Mesh(BaseModel):
    positions: list[float]  # x, y, z per vertex, in the file's units
    indices: list[int]  # three vertex indices per triangle
    faces: list[FaceRange] = []
    bbox: tuple[float, float, float, float, float, float]


def _bbox(positions: list[float]) -> tuple[float, float, float, float, float, float]:
    xs, ys, zs = positions[0::3], positions[1::3], positions[2::3]
    return min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)


def mesh_brep(data: bytes, kind: str) -> Mesh:
    from OCP.Bnd import Bnd_Box
    from OCP.BRep import BRep_Tool
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.IFSelect import IFSelect_ReturnStatus
    from OCP.IGESControl import IGESControl_Reader
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS

    _quiet_ocp()
    reader = STEPControl_Reader() if kind == "step" else IGESControl_Reader()
    with _temp_file(data, ".step" if kind == "step" else ".igs") as path:
        if reader.ReadFile(path) != IFSelect_ReturnStatus.IFSelect_RetDone:
            raise ValueError(f"OCP could not read the {kind.upper()} file")
    reader.TransferRoots()
    shape = reader.OneShape()
    model = reader.WS().Model()
    transfer = reader.WS().TransferReader()
    numbers = {model.Value(i): i for i in range(1, model.NbEntities() + 1)}

    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    lo, hi = box.CornerMin(), box.CornerMax()
    diag = lo.Distance(hi) or 1.0
    BRepMesh_IncrementalMesh(shape, LINEAR_DEFLECTION * diag, False, ANGULAR_DEFLECTION_RAD, True)

    positions: list[float] = []
    indices: list[int] = []
    faces: list[FaceRange] = []
    fx = TopExp_Explorer(shape, TopAbs_FACE)
    while fx.More():
        face = TopoDS.Face(fx.Current())
        location = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, location)
        if tri is not None:
            trsf = location.Transformation()
            base = len(positions) // 3
            for i in range(1, tri.NbNodes() + 1):
                p = tri.Node(i).Transformed(trsf)
                positions += [p.X(), p.Y(), p.Z()]
            reverse = face.Orientation() == TopAbs_REVERSED
            start = len(indices) // 3
            for i in range(1, tri.NbTriangles() + 1):
                a, b, c = tri.Triangle(i).Get()
                if reverse:
                    b, c = c, b
                indices += [base + a - 1, base + b - 1, base + c - 1]
            ent = transfer.EntityFromShapeResult(face, 1)
            n = numbers.get(ent) if ent is not None else None
            handle = None if n is None else (f"#{n}" if kind == "step" else f"DE{2 * n - 1}")
            faces.append(FaceRange(handle=handle, start=start, count=tri.NbTriangles()))
        fx.Next()
    if not indices:
        raise ValueError("the model has no faces to draw")
    return Mesh(positions=positions, indices=indices, faces=faces, bbox=_bbox(positions))


def mesh_stl(data: bytes) -> Mesh:
    import trimesh

    m = trimesh.load(io.BytesIO(data), file_type="stl", force="mesh")
    if not isinstance(m, trimesh.Trimesh):
        raise ValueError("the STL file holds no triangle mesh")
    positions = [float(v) for v in m.vertices.reshape(-1)]
    indices = [int(i) for i in m.faces.reshape(-1)]
    return Mesh(positions=positions, indices=indices, bbox=_bbox(positions))


def mesh_of(data: bytes, kind: str) -> Mesh:
    if kind in ("step", "iges"):
        return mesh_brep(data, kind)
    if kind == "stl":
        return mesh_stl(data)
    raise ValueError(f"no 3D mesh for {kind} input")


"""Synthetic 3D models (STEP and STL) with exact ground truth (plan Phase 0 task 2: "20 STEP/STL models").

Each model is a plate or sheet-metal bracket from ``parts.sample`` (the same families as the
drawings), built as a solid with OCP and written as STEP and as STL. Lengths are in mm.

- Plate: L x W x T box with through holes, and a through slot when the part has one.
- Bracket: horizontal flange B x W x t and vertical flange t x W x H joined at the back edge
  (the bend is modelled sharp; its radius is a 2D drawing feature), with one through hole
  in the horizontal flange.

``<id>.model.json`` holds the truth: bounding box, volume, holes (diameter, centre x and y
from the part's corner) and the number of through openings (holes plus slot), which equals
the genus of the STL mesh.
"""

import json
import random
from pathlib import Path

from pydantic import BaseModel

from edp_eval.golden import GoldenItem, GoldenManifest, Provenance
from edp_eval.synth.parts import FAMILIES, Bracket, Plate, sample

LINEAR_DEFLECTION_MM = 0.05  # STL tessellation fineness


class ModelHole(BaseModel):
    diameter: float
    x: float
    y: float


class ModelLabel(BaseModel):
    schema_version: str = "0.1.0"
    id: str
    family: str
    bbox: tuple[float, float, float, float, float, float]
    volume: float
    holes: list[ModelHole]
    through_openings: int


def _build(part: Plate | Bracket):  # noqa: ANN202 - OCP shape
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    def box(x, y, z, dx, dy, dz):  # noqa: ANN001, ANN202
        return BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), dx, dy, dz).Shape()

    def drill(shape, x, y, d, depth):  # noqa: ANN001, ANN202
        cyl = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, -1.0), gp_Dir(0, 0, 1)), d / 2, depth + 2).Shape()
        return BRepAlgoAPI_Cut(shape, cyl).Shape()

    holes: list[ModelHole] = []
    openings = 0
    if isinstance(part, Plate):
        shape = box(0, 0, 0, part.length, part.width, part.thickness)
        for h in part.holes:
            shape = drill(shape, h.x, h.y, h.diameter, part.thickness)
            holes.append(ModelHole(diameter=h.diameter, x=h.x, y=h.y))
            openings += 1
        if part.slot_length and part.slot_width:
            r = part.slot_width / 2
            cx, cy = part.length / 2, part.width / 2
            x0, x1 = cx - part.slot_length / 2 + r, cx + part.slot_length / 2 - r
            cutter = BRepAlgoAPI_Fuse(
                box(x0, cy - r, -1, x1 - x0, 2 * r, part.thickness + 2),
                BRepPrimAPI_MakeCylinder(
                    gp_Ax2(gp_Pnt(x0, cy, -1), gp_Dir(0, 0, 1)), r, part.thickness + 2
                ).Shape(),
            ).Shape()
            cutter = BRepAlgoAPI_Fuse(
                cutter,
                BRepPrimAPI_MakeCylinder(
                    gp_Ax2(gp_Pnt(x1, cy, -1), gp_Dir(0, 0, 1)), r, part.thickness + 2
                ).Shape(),
            ).Shape()
            shape = BRepAlgoAPI_Cut(shape, cutter).Shape()
            openings += 1
    else:
        t = part.thickness
        shape = BRepAlgoAPI_Fuse(
            box(0, 0, 0, part.flange_b, part.width, t), box(0, 0, 0, t, part.width, part.flange_a)
        ).Shape()
        shape = drill(shape, part.hole.x, part.hole.y, part.hole.diameter, t)
        holes.append(ModelHole(diameter=part.hole.diameter, x=part.hole.x, y=part.hole.y))
        openings = 1
    return shape, holes, openings


def write_model_set(out: Path, count: int, seed: int, uri_prefix: str) -> GoldenManifest:
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepGProp import BRepGProp
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.GProp import GProp_GProps
    from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
    from OCP.StlAPI import StlAPI_Writer

    from edp_b1_parser.model3d import _quiet_ocp

    _quiet_ocp()
    out.mkdir(parents=True, exist_ok=True)
    prefix = uri_prefix.rstrip("/")
    items = []
    for i in range(count):
        family = FAMILIES[i % 2]
        part = sample(family, random.Random(f"{seed}-model-{i}"))
        shape, holes, openings = _build(part)
        box = Bnd_Box()
        BRepBndLib.Add_s(shape, box, False)  # exact box, without tolerance gaps
        lo, hi = box.CornerMin(), box.CornerMax()
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(shape, props)
        mid = f"model-{family}-{i:03d}"
        label = ModelLabel(
            id=mid,
            family=family,
            bbox=(lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()),
            volume=props.Mass(),
            holes=holes,
            through_openings=openings,
        )
        writer = STEPControl_Writer()
        writer.Transfer(shape, STEPControl_AsIs)
        writer.Write(str(out / f"{mid}.step"))
        BRepMesh_IncrementalMesh(shape, LINEAR_DEFLECTION_MM, False, 0.2, True)
        stl = StlAPI_Writer()
        stl.ASCIIMode = False
        stl.Write(shape, str(out / f"{mid}.stl"))
        (out / f"{mid}.model.json").write_text(label.model_dump_json(indent=2), encoding="utf-8")
        for ext, fmt in (("step", "step"), ("stl", "stl")):
            items.append(
                GoldenItem(
                    id=f"{mid}-{ext}",
                    input_format=fmt,
                    part_family=family,  # type: ignore[arg-type]
                    provenance=Provenance(kind="internal"),
                    data_uri=f"{prefix}/{mid}.{ext}",
                    ground_truth_uri=f"{prefix}/{mid}.model.json",
                    labelled=True,
                    label_fields=["geometry", "expected_parameters"],
                )
            )
    manifest = GoldenManifest(version=f"models-seed{seed}-n{count}", items=items)
    (out / "manifest.json").write_text(json.dumps(manifest.model_dump(), indent=2), encoding="utf-8")
    return manifest

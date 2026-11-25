"""``geometry`` artifact, schema v0.2.

Source: plan Phase 2, key tasks 1 and 3. The unified geometry artifact holds
entities (line, arc, circle, spline, text, dimension), views, units, scale and
locators. The title block holds part number, revision, material, scale, units
and tolerances, with per-field confidence.

Every entity carries a required locator: the Phase 2 exit criterion is 100 %
of entities with a valid source locator.

Schema 0.2.0 (additive, plan §3 versioning) adds ``solids`` for 3D inputs, from
plan Phase 2 "Approach by input": STEP and IGES give a "topology walk (faces,
edges, holes), STEP entity ids as locators"; STL gives "watertightness, bounding
box, feature hints" and is flagged as a lossy input.
"""

from typing import Literal

from pydantic import BaseModel

from edp_contracts.block import SourceLocator

SCHEMA_VERSION = "0.2.0"

EntityKind = Literal["line", "arc", "circle", "spline", "text", "dimension"]


class GeometryEntity(BaseModel):
    kind: EntityKind
    locator: SourceLocator
    data: dict = {}  # kind-specific values; typed per kind in a later version


class TitleBlockField(BaseModel):
    value: str | None = None
    locator: SourceLocator  # confidence lives on the locator


class TitleBlock(BaseModel):
    part_number: TitleBlockField | None = None
    revision: TitleBlockField | None = None
    material: TitleBlockField | None = None
    scale: TitleBlockField | None = None
    units: TitleBlockField | None = None
    tolerances: TitleBlockField | None = None


class Hole3D(BaseModel):
    """A cylindrical bore: the material is outside the cylinder (its axis lies outside the solid)."""

    diameter: float
    axis_origin: tuple[float, float, float]
    axis_direction: tuple[float, float, float]
    locators: list[SourceLocator]  # one per face (a bore is often split into two half faces)


class Solid(BaseModel):
    locator: SourceLocator  # STEP: the solid's entity id; STL: the mesh
    bbox: tuple[float, float, float, float, float, float]  # xmin, ymin, zmin, xmax, ymax, zmax
    volume: float | None = None
    faces: dict[str, int] = {}  # face count by surface type (plane, cylinder, ...)
    edges: int | None = None
    holes: list[Hole3D] = []
    watertight: bool | None = None  # meshes only
    through_holes_hint: int | None = None  # meshes: genus of a closed mesh, a hint only
    lossy: bool = False  # True for meshes (STL)


class Geometry(BaseModel):
    schema_version: str = SCHEMA_VERSION
    views: list[str] = []
    units: str | None = None
    scale: str | None = None
    entities: list[GeometryEntity] = []
    title_block: TitleBlock | None = None
    solids: list[Solid] = []  # 3D inputs (schema 0.2.0)

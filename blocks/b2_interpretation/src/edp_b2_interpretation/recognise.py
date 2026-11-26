"""Rule-based feature recognition from 2D geometry (plan Phase 3, Interpretation task 2: "rule-based first").

Also the dimension association of plan Phase 2 task 2: "link each dimension to the
features it measures, using geometry first".

Rules for the R1 families (plan Phase 0 task 3; OD-12 working assumption):

- **hole**: a full CIRCLE. Diameter from a diameter DIMENSION at the same centre.
  Position x, y from the bottom-left corner of the closed outline that contains
  it, from linear DIMENSIONs whose two measured coordinates are that corner and the
  hole centre along one axis.
- **slot**: two 180-degree ARCs of equal radius facing away from each other.
  Length end to end and width across, from linear DIMENSIONs at those coordinates.
- **bend**: two concentric ARCs with the same sweep. Inner radius from a radius
  DIMENSION at that centre; thickness = outer - inner radius.

Each parameter records how its value was found:

| association | meaning | confidence |
|---|---|---|
| ``geometric`` | a dimension measures this feature's points | 1.0 |
| ``by_value`` | a dimension has the same value, no geometric link | 0.9 |
| ``geometry_only`` | no dimension; value taken from the geometry | 0.7, plus a LOW_CONFIDENCE flag |

The confidences are starting values for calibration (plan Phase 2 task 5).
``REL_TOL`` is the coincidence tolerance; exact for CAD-written files, to be
checked on real drawings (OD-45).
"""

import math
from dataclasses import dataclass, field
from typing import Literal

from edp_contracts import Flag, SourceLocator
from edp_contracts.artifacts.geometry import Geometry, GeometryEntity

REL_TOL = 1e-6
CONFIDENCE = {"geometric": 1.0, "by_value": 0.9, "geometry_only": 0.7}
Association = Literal["geometric", "by_value", "geometry_only"]


def close(a: float, b: float) -> bool:
    return abs(a - b) <= REL_TOL * max(1.0, abs(a), abs(b))


def close_pt(a: list[float], b: list[float]) -> bool:
    return close(a[0], b[0]) and close(a[1], b[1])


@dataclass
class Param:
    name: str
    value: float
    association: Association
    sources: list[SourceLocator]
    dimension_handles: list[str] = field(default_factory=list)

    @property
    def confidence(self) -> float:
        return CONFIDENCE[self.association]


@dataclass
class Feature:
    type: Literal["hole", "slot", "bend"]
    params: dict[str, Param]
    sources: list[SourceLocator]


@dataclass
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float
    locator: SourceLocator

    def contains(self, x: float, y: float) -> bool:
        return self.x0 < x < self.x1 and self.y0 < y < self.y1

    @property
    def area(self) -> float:
        return (self.x1 - self.x0) * (self.y1 - self.y0)


@dataclass
class Recognition:
    features: list[Feature]
    unassociated: list[GeometryEntity]  # dimensions linked to no feature (part-level)
    flags: list[Flag]
    # Part-level dimensions that measure a whole outline: handle -> "length", "width" or
    # "thickness". Block 4 (Generation) needs the overall size of a plate (plan Phase 4).
    outline_roles: dict[str, str] = field(default_factory=dict)


def _rectangles(entities: list[GeometryEntity]) -> list[Rect]:
    groups: dict[str, list[GeometryEntity]] = {}
    for e in entities:
        if e.kind == "line" and e.data.get("from") == "LWPOLYLINE" and e.locator.handle:
            groups.setdefault(e.locator.handle, []).append(e)
    rects = []
    for parts in groups.values():
        pts = [p for e in parts for p in (e.data["start"], e.data["end"])]
        axis_aligned = all(
            close(e.data["start"][0], e.data["end"][0]) or close(e.data["start"][1], e.data["end"][1])
            for e in parts
        )
        if len(parts) == 4 and axis_aligned:
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            rects.append(Rect(min(xs), min(ys), max(xs), max(ys), parts[0].locator))
    return rects


def _linear(dims: list[GeometryEntity], axis: int, a: float, b: float) -> list[GeometryEntity]:
    """Linear dimensions along ``axis`` (0 = x, 1 = y) whose two measured coordinates are a and b."""
    want = sorted((a, b))
    out = []
    for d in dims:
        if d.data.get("dimtype") not in ("linear", "aligned") or "p1" not in d.data:
            continue
        angle = d.data.get("angle", 0.0) % 180
        if not (close(angle, 0.0) if axis == 0 else close(angle, 90.0)):
            continue
        got = sorted((d.data["p1"][axis], d.data["p2"][axis]))
        if close(got[0], want[0]) and close(got[1], want[1]):
            out.append(d)
    return out


class _Recogniser:
    def __init__(self, geometry: Geometry) -> None:
        self.entities = geometry.entities
        self.dims = [e for e in self.entities if e.kind == "dimension"]
        self.used: set[str] = set()
        self.flags: list[Flag] = []

    def param(
        self,
        name: str,
        geometric_value: float,
        dims: list[GeometryEntity],
        base: list[SourceLocator],
        owner: str,
        association_if_found: Association = "geometric",
    ) -> Param:
        if dims:
            values = {round(d.data["value"], 9) for d in dims}
            if len(values) > 1:
                self.flags.append(
                    Flag(
                        code="CONTRADICTION",
                        target=dims[0].locator,
                        message=f"{owner}.{name}: dimensions disagree {sorted(values)}",
                    )
                )
            if association_if_found == "geometric":
                self.used.update(d.locator.handle or "" for d in dims)
            return Param(
                name,
                float(dims[0].data["value"]),
                association_if_found,
                [d.locator for d in dims] + base,
                [d.locator.handle or "" for d in dims],
            )
        self.flags.append(
            Flag(
                code="LOW_CONFIDENCE",
                target=base[0] if base else None,
                message=f"[UNDIMENSIONED] {owner}.{name} taken from geometry ({geometric_value:g})",
            )
        )
        return Param(name, geometric_value, "geometry_only", list(base))

    def holes(self, rects: list[Rect]) -> list[Feature]:
        out = []
        for c in (e for e in self.entities if e.kind == "circle"):
            (cx, cy), r = c.data["center"], c.data["radius"]
            owner = f"hole@{cx:g},{cy:g}"
            dia = [
                d
                for d in self.dims
                if d.data.get("dimtype") == "diameter"
                and "center" in d.data
                and close_pt(d.data["center"], [cx, cy])
                and close(d.data["measurement"], 2 * r)
            ]
            params = {"diameter": self.param("diameter", 2 * r, dia, [c.locator], owner)}
            inside = [rc for rc in rects if rc.contains(cx, cy)]
            if inside:
                rect = min(inside, key=lambda rc: rc.area)
                if cx - r < rect.x0 or cx + r > rect.x1 or cy - r < rect.y0 or cy + r > rect.y1:
                    self.flags.append(
                        Flag(
                            code="FEATURE_OUTSIDE_PART",
                            target=c.locator,
                            message=f"{owner} extends beyond its outline",
                        )
                    )
                base = [c.locator, rect.locator]
                params["x"] = self.param("x", cx - rect.x0, _linear(self.dims, 0, rect.x0, cx), base, owner)
                params["y"] = self.param("y", cy - rect.y0, _linear(self.dims, 1, rect.y0, cy), base, owner)
            else:
                self.flags.append(
                    Flag(
                        code="LOW_CONFIDENCE",
                        target=c.locator,
                        message=f"[NO_DATUM] {owner}: no closed outline around the hole",
                    )
                )
            out.append(Feature("hole", params, [c.locator]))
        return out

    def slots(self) -> list[Feature]:
        halves = [a for a in self.entities if a.kind == "arc" and close(_sweep(a), 180.0)]
        out, taken = [], set()
        for i, a in enumerate(halves):
            for j in range(i + 1, len(halves)):
                b = halves[j]
                if i in taken or j in taken or not close(a.data["radius"], b.data["radius"]):
                    continue
                (ax, ay), (bx, by), r = a.data["center"], b.data["center"], a.data["radius"]
                dist = math.hypot(bx - ax, by - ay)
                if dist == 0:
                    continue
                ux, uy = (bx - ax) / dist, (by - ay) / dist
                if not (_faces(a, -ux, -uy) and _faces(b, ux, uy)):
                    continue
                taken |= {i, j}
                owner = f"slot@{(ax + bx) / 2:g},{(ay + by) / 2:g}"
                axis = 0 if close(uy, 0.0) else 1 if close(ux, 0.0) else None
                base = [a.locator, b.locator]
                if axis is None:
                    length_dims: list[GeometryEntity] = []
                    width_dims: list[GeometryEntity] = []
                else:
                    lo, hi = sorted(((ax, ay)[axis], (bx, by)[axis]))
                    across = (ay, ax)[axis]
                    length_dims = _linear(self.dims, axis, lo - r, hi + r)
                    width_dims = _linear(self.dims, 1 - axis, across - r, across + r)
                params = {
                    "length": self.param("length", dist + 2 * r, length_dims, base, owner),
                    "width": self.param("width", 2 * r, width_dims, base, owner),
                }
                out.append(Feature("slot", params, base))
        return out

    def bends(self) -> list[Feature]:
        arcs = [a for a in self.entities if a.kind == "arc" and not close(_sweep(a), 180.0)]
        out, taken = [], set()
        for i, a in enumerate(arcs):
            for j in range(len(arcs)):
                b = arcs[j]
                if i == j or i in taken or j in taken:
                    continue
                if not (
                    close_pt(a.data["center"], b.data["center"])
                    and close(_sweep(a), _sweep(b))
                    and close(a.data["start_angle"], b.data["start_angle"])
                    and a.data["radius"] < b.data["radius"]
                ):
                    continue
                taken |= {i, j}
                inner, thick = a.data["radius"], b.data["radius"] - a.data["radius"]
                owner = f"bend@{a.data['center'][0]:g},{a.data['center'][1]:g}"
                rdims = [
                    d
                    for d in self.dims
                    if d.data.get("dimtype") == "radius"
                    and "center" in d.data
                    and close_pt(d.data["center"], a.data["center"])
                    and close(d.data["measurement"], inner)
                ]
                tdims = [
                    d
                    for d in self.dims
                    if d.data.get("dimtype") in ("linear", "aligned") and close(d.data["measurement"], thick)
                ]
                base = [a.locator, b.locator]
                params = {
                    "radius": self.param("radius", inner, rdims, base, owner),
                    "thickness": self.param("thickness", thick, tdims, base, owner, "by_value"),
                }
                out.append(Feature("bend", params, base))
        return out


def _sweep(arc: GeometryEntity) -> float:
    return (arc.data["end_angle"] - arc.data["start_angle"]) % 360 or 360.0


def _faces(arc: GeometryEntity, dx: float, dy: float) -> bool:
    """True when the arc's middle points in direction (dx, dy)."""
    mid = math.radians(arc.data["start_angle"] + _sweep(arc) / 2)
    return close(math.cos(mid) * dx + math.sin(mid) * dy, 1.0)


def outline_roles(rects: list[Rect], dims: list[GeometryEntity], features: list[Feature]) -> dict[str, str]:
    """Name the dimensions that measure a plate's whole outline.

    A plate is drawn as a plan view (the rectangle that holds its holes or slots) and an edge
    view (another rectangle with the same x extent). A linear dimension across the plan view's
    x extent is the length, across its y extent the width, and across the edge view's y extent
    the thickness. Other parts (brackets) have no such pair and get no roles.
    """
    plan = None
    for rect in sorted(rects, key=lambda rc: -rc.area):
        if any(_feature_inside(f, rect) for f in features):
            plan = rect
            break
    if plan is None:
        return {}
    edge = next(
        (
            rc
            for rc in rects
            if rc is not plan and close(rc.x0, plan.x0) and close(rc.x1, plan.x1) and rc.area < plan.area
        ),
        None,
    )
    roles: dict[str, str] = {}
    for d in _linear(dims, 0, plan.x0, plan.x1):
        roles[d.locator.handle or ""] = "length"
    for d in _linear(dims, 1, plan.y0, plan.y1):
        roles[d.locator.handle or ""] = "width"
    if edge is not None:
        for d in _linear(dims, 1, edge.y0, edge.y1):
            roles[d.locator.handle or ""] = "thickness"
    roles.pop("", None)
    return roles


def _feature_inside(f: Feature, rect: Rect) -> bool:
    for loc in f.sources:
        if loc.bbox is not None:
            cx, cy = (loc.bbox[0] + loc.bbox[2]) / 2, (loc.bbox[1] + loc.bbox[3]) / 2
            if rect.contains(cx, cy):
                return True
    return False


def recognise(geometry: Geometry) -> Recognition:
    r = _Recogniser(geometry)
    rects = _rectangles(geometry.entities)
    features = r.holes(rects) + r.slots() + r.bends()
    unassociated = [d for d in r.dims if (d.locator.handle or "") not in r.used]
    roles = outline_roles(rects, unassociated, features)
    return Recognition(features=features, unassociated=unassociated, flags=r.flags, outline_roles=roles)

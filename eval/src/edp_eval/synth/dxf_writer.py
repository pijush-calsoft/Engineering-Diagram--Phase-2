"""Write synthetic DXF drawings with exact ground truth (OD-7: create a golden set).

Each drawing has two orthographic views, DIMENSION entities and a title block.
Every label carries the DXF handle of the entity it describes, which is the
source locator the Drawing Parser must report (plan Phase 2 task 1, principle 1).
ezdxf is the plan's DXF library (plan §4.2 block 1).
"""

import random
import re
from pathlib import Path

import ezdxf
from ezdxf.document import Drawing
from ezdxf.layouts import Modelspace

from edp_eval.synth.labels import DimensionKind, LabelDimension, LabelText, SyntheticLabel
from edp_eval.synth.parts import Bracket, Family, Hole, Part, Plate, sample
from edp_eval.synth.profiles import PROFILES, DrawingProfile

LAYERS = ("GEOMETRY", "DIMENSIONS", "TITLE", "NOTES")
MEASUREMENT_TOL = 1e-6
_NUMBER = re.compile(r"\d*\.?\d+")


class _Sheet:
    def __init__(self, profile: DrawingProfile) -> None:
        self.p = profile
        self.doc: Drawing = ezdxf.new("R2010", setup=True, units=profile.insunits)
        self.doc.header["$MEASUREMENT"] = profile.measurement
        for name in LAYERS:
            self.doc.layers.add(name)
        self.msp: Modelspace = self.doc.modelspace()
        self.dims: list[LabelDimension] = []
        # dimlfac = 1: the "EZDXF" and "EZ_RADIUS" styles ship with dimlfac = 100, which would
        # display 100 times the measured value.
        self.override = {
            "dimtxt": profile.text_height,
            "dimasz": profile.arrow_size,
            "dimdec": profile.decimals,
            "dimlfac": 1.0,
        }

    @property
    def gap(self) -> float:
        return 4 * self.p.text_height

    def u(self, value_mm: float) -> float:
        return self.p.convert(value_mm)

    def rect(self, x0: float, y0: float, w: float, h: float) -> None:
        self.msp.add_lwpolyline(
            [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)],
            close=True,
            dxfattribs={"layer": "GEOMETRY"},
        )

    def _record(self, dim: object, kind: DimensionKind, target: str, view: str, value: float) -> None:
        entity = dim.dimension  # type: ignore[attr-defined]
        measured = entity.get_measurement()
        if abs(measured - value) > MEASUREMENT_TOL:
            raise AssertionError(f"{target}: drawn {measured}, label {value}")
        self.dims.append(
            LabelDimension(target=target, value=value, kind=kind, view=view, handle=entity.dxf.handle)
        )

    def linear(
        self,
        target: str,
        view: str,
        p1: tuple[float, float],
        p2: tuple[float, float],
        base: tuple[float, float],
        angle: float,
        value: float,
    ) -> None:
        dim = self.msp.add_linear_dim(
            base=base,
            p1=p1,
            p2=p2,
            angle=angle,
            dimstyle="EZDXF",
            override=self.override,
            dxfattribs={"layer": "DIMENSIONS"},
        )
        dim.render()
        self._record(dim, "linear", target, view, value)

    def diameter(self, target: str, view: str, center: tuple[float, float], d: float) -> None:
        dim = self.msp.add_diameter_dim(
            center=center,
            radius=d / 2,
            angle=45,
            dimstyle="EZ_RADIUS",
            override=self.override,
            dxfattribs={"layer": "DIMENSIONS"},
        )
        dim.render()
        self._record(dim, "diameter", target, view, d)

    def radius(self, target: str, view: str, center: tuple[float, float], r: float, angle: float) -> None:
        dim = self.msp.add_radius_dim(
            center=center,
            radius=r,
            angle=angle,
            dimstyle="EZ_RADIUS",
            override=self.override,
            dxfattribs={"layer": "DIMENSIONS"},
        )
        dim.render()
        self._record(dim, "radius", target, view, r)

    def text(self, value: str, at: tuple[float, float], layer: str) -> str:
        t = self.msp.add_text(value, height=self.p.text_height, dxfattribs={"layer": layer})
        t.set_placement(at)
        return str(t.dxf.handle)


def _plan_view_y(profile: DrawingProfile, front_height: float, plan_height: float, gap: float) -> float:
    # First-angle (ISO): the view from above sits below the front view. Third-angle (ASME): above it.
    return -(plan_height + 4 * gap) if profile.projection == "first_angle" else front_height + 4 * gap


def _hole_dims(s: _Sheet, holes: tuple[Hole, ...], ox: float, oy: float, view: str) -> None:
    # Each distinct x and y position is dimensioned once, from the bottom-left datum corner,
    # and labelled with the first hole that has it.
    seen_x: set[float] = set()
    seen_y: set[float] = set()
    for i, h in enumerate(holes, start=1):
        x, y, d = s.u(h.x), s.u(h.y), s.u(h.diameter)
        c = (ox + x, oy + y)
        s.msp.add_circle(c, d / 2, dxfattribs={"layer": "GEOMETRY"})
        s.diameter(f"hole{i}.diameter", view, c, d)
        if x not in seen_x:
            s.linear(f"hole{i}.x", view, (ox, oy), c, (ox, oy - (1 + len(seen_x)) * s.gap), 0, x)
            seen_x.add(x)
        if y not in seen_y:
            s.linear(f"hole{i}.y", view, (ox, oy), c, (ox - (1 + len(seen_y)) * s.gap, oy), 90, y)
            seen_y.add(y)


def _draw_plate(s: _Sheet, part: Plate) -> dict[str, float]:
    L, W, T = s.u(part.length), s.u(part.width), s.u(part.thickness)
    s.rect(0, 0, L, T)  # front view
    s.linear("plate.length", "front", (0, T), (L, T), (0, T + s.gap), 0, L)
    s.linear("plate.thickness", "front", (L, 0), (L, T), (L + s.gap, 0), 90, T)
    py = _plan_view_y(s.p, T, W, s.gap)
    s.rect(0, py, L, W)  # view from above
    s.linear("plate.width", "top", (L, py), (L, py + W), (L + s.gap, py), 90, W)
    _hole_dims(s, part.holes, 0, py, "top")
    params = {"length": L, "width": W, "thickness": T, "hole_count": float(len(part.holes))}
    if part.slot_length and part.slot_width:
        sl, sw = s.u(part.slot_length), s.u(part.slot_width)
        cx, cy, r = L / 2, py + W / 2, sw / 2
        x0, x1 = cx - sl / 2 + r, cx + sl / 2 - r
        s.msp.add_line((x0, cy - r), (x1, cy - r), dxfattribs={"layer": "GEOMETRY"})
        s.msp.add_line((x0, cy + r), (x1, cy + r), dxfattribs={"layer": "GEOMETRY"})
        s.msp.add_arc((x0, cy), r, 90, 270, dxfattribs={"layer": "GEOMETRY"})
        s.msp.add_arc((x1, cy), r, 270, 90, dxfattribs={"layer": "GEOMETRY"})
        s.linear("slot.length", "top", (cx - sl / 2, cy), (cx + sl / 2, cy), (cx, py + W + s.gap), 0, sl)
        s.linear("slot.width", "top", (cx, cy - r), (cx, cy + r), (x1 + r + s.gap, cy), 90, sw)
        params |= {"slot_length": sl, "slot_width": sw}
    if part.holes:
        params["hole_diameter"] = s.u(part.holes[0].diameter)
    return params


def _draw_bracket(s: _Sheet, part: Bracket) -> dict[str, float]:
    H, B, W = s.u(part.flange_a), s.u(part.flange_b), s.u(part.width)
    t, r = s.u(part.thickness), s.u(part.bend_radius)
    c = (t + r, t + r)  # bend centre, front view
    g = {"layer": "GEOMETRY"}
    s.msp.add_line((0, H), (0, t + r), dxfattribs=g)
    s.msp.add_arc(c, r + t, 180, 270, dxfattribs=g)
    s.msp.add_line((t + r, 0), (B, 0), dxfattribs=g)
    s.msp.add_line((B, 0), (B, t), dxfattribs=g)
    s.msp.add_line((B, t), (t + r, t), dxfattribs=g)
    s.msp.add_arc(c, r, 180, 270, dxfattribs=g)
    s.msp.add_line((t, t + r), (t, H), dxfattribs=g)
    s.msp.add_line((t, H), (0, H), dxfattribs=g)
    s.linear("bracket.flange_a", "front", (0, 0), (0, H), (-s.gap, 0), 90, H)
    s.linear("bracket.flange_b", "front", (0, 0), (B, 0), (0, -s.gap), 0, B)
    s.linear("bracket.thickness", "front", (0, H), (t, H), (0, H + s.gap), 0, t)
    s.radius("bracket.bend_radius", "front", c, r, 225)
    py = _plan_view_y(s.p, H, W, s.gap)
    s.rect(0, py, B, W)  # view from above
    s.linear("bracket.width", "top", (B, py), (B, py + W), (B + s.gap, py), 90, W)
    _hole_dims(s, (part.hole,), 0, py, "top")
    return {
        "flange_a": H,
        "flange_b": B,
        "width": W,
        "thickness": t,
        "bend_radius": r,
        "hole_diameter": s.u(part.hole.diameter),
        "hole_x": s.u(part.hole.x),
        "hole_y": s.u(part.hole.y),
    }


def _title_block(s: _Sheet, index: int, rng: random.Random, x: float, y: float) -> dict[str, LabelText]:
    values = {
        "part_number": f"EDP-SYN-{index:04d}",
        "revision": rng.choice(("A", "B", "C")),
        "material": rng.choice(s.p.materials),
        "scale": "1:1",
        "units": s.p.units.upper(),
        "tolerances": s.p.general_tolerance,
    }
    out: dict[str, LabelText] = {}
    step = 2 * s.p.text_height
    for i, (key, value) in enumerate(values.items()):
        handle = s.text(f"{key.replace('_', ' ').upper()}: {value}", (x, y - i * step), "TITLE")
        out[key] = LabelText(value=value, handle=handle)
    return out


def generate(
    profile: DrawingProfile, family: Family, index: int, seed: int
) -> tuple[Drawing, SyntheticLabel]:
    rng = random.Random(f"{seed}-{index}")
    part: Part = sample(family, rng)
    s = _Sheet(profile)
    params = _draw_plate(s, part) if isinstance(part, Plate) else _draw_bracket(s, part)
    extent = max(params.get("length", 0.0), params.get("flange_b", 0.0))
    s.text(f"{profile.projection.replace('_', ' ').upper()} PROJECTION", (extent + 8 * s.gap, 0), "NOTES")
    title = _title_block(s, index, rng, extent + 8 * s.gap, -4 * s.gap)
    label = SyntheticLabel(
        id=f"syn-{profile.name}-{family}-{index:03d}",
        family=family,
        profile=profile.name,
        projection=profile.projection,
        units=profile.units,
        seed=seed,
        views=["front", "top"],
        parameters=params,
        dimensions=s.dims,
        title_block=title,
    )
    return s.doc, label


def verify(dxf_path: Path, label: SyntheticLabel) -> list[str]:
    """Re-read a written drawing and check every label against the DXF entities.

    Checks the measured geometry and the displayed dimension text, which is what a
    parser reads, and the title-block text.
    """
    doc = ezdxf.readfile(dxf_path)
    decimals = PROFILES[label.profile].decimals  # type: ignore[index]
    errors: list[str] = []
    for d in label.dimensions:
        e = doc.entitydb.get(d.handle)
        if e is None or e.dxftype() != "DIMENSION":
            errors.append(f"{d.target}: no DIMENSION with handle {d.handle}")
            continue
        measured = e.get_measurement()  # type: ignore[attr-defined]
        if abs(measured - d.value) > MEASUREMENT_TOL:
            errors.append(f"{d.target}: measured {measured}, label {d.value}")
        shown = _displayed_value(e)
        if shown is None or abs(shown - round(d.value, decimals)) > MEASUREMENT_TOL:
            errors.append(f"{d.target}: displayed {shown}, label {d.value}")
    for key, t in label.title_block.items():
        e = doc.entitydb.get(t.handle)
        if e is None or e.dxftype() != "TEXT" or not e.dxf.text.endswith(f": {t.value}"):
            errors.append(f"title_block.{key}: text with handle {t.handle} does not hold {t.value!r}")
    return errors


def _displayed_value(dimension: object) -> float | None:
    """The number shown in a rendered DIMENSION's text, or None if it has none."""
    block = dimension.get_geometry_block()  # type: ignore[attr-defined]
    if block is None:
        return None
    for e in block:
        if e.dxftype() == "MTEXT":
            m = _NUMBER.search(e.plain_text())
            return float(m.group()) if m else None
    return None

"""DXF extraction with ezdxf (plan Phase 2, "Approach by input": DXF).

"iterate modelspace and layouts, resolve blocks and inserts, read DIMENSION
entities and their measurements, keep entity handles as locators" (plan Phase 2).

- Polylines and block inserts are resolved to their LINE/ARC/... parts. The
  parts keep the handle of the source entity, which is what exists in the file.
- A DIMENSION reports the value its text displays and the measured geometry.
  When they differ (text typed over), a ``DIM_TEXT_MISMATCH`` review flag is raised.
- Every entity carries a locator: file id, version, layout as view, layer,
  handle, bounding box in drawing units. Values read directly from the file get
  confidence 1.0; calibration is measured on the golden set (Phase 2 task 5).
"""

import io
import re
from collections import Counter
from typing import Any

from ezdxf import bbox, recover
from ezdxf.entities import DXFGraphic
from ezdxf.lldxf import const

from edp_b1_parser.dxf_raw import raw_dimensions
from edp_b1_parser.title_block import TextItem, extract
from edp_contracts import Flag, SourceLocator
from edp_contracts.artifacts.geometry import Geometry, GeometryEntity

# DXF $INSUNITS codes (DXF reference) for the units R1 drawings use.
INSUNITS = {1: "in", 2: "ft", 4: "mm", 5: "cm", 6: "m"}
DIMTYPES = {
    0: "linear",
    1: "aligned",
    2: "angular",
    3: "diameter",
    4: "radius",
    5: "angular_3p",
    6: "ordinate",
}
_KINDS = {
    "LINE": "line",
    "ARC": "arc",
    "CIRCLE": "circle",
    "SPLINE": "spline",
    "TEXT": "text",
    "MTEXT": "text",
    "DIMENSION": "dimension",
}
_NUMBER = re.compile(r"[-+]?\d*\.?\d+")
MEASUREMENT_TOL = 1e-6
_UNIT_WORDS = {
    w: code
    for code, words in {
        "mm": ("mm", "millimetre", "millimetres", "millimeter", "millimeters"),
        "cm": ("cm", "centimetre", "centimetres", "centimeter", "centimeters"),
        "m": ("m", "metre", "metres", "meter", "meters"),
        "in": ("in", "inch", "inches", '"'),
        "ft": ("ft", "foot", "feet"),
    }.items()
    for w in words
}


class _Reader:
    def __init__(self, file_id: str, version: str) -> None:
        self.file_id, self.version = file_id, version
        self.entities: list[GeometryEntity] = []
        self.texts: list[TextItem] = []
        self.flags: list[Flag] = []
        self.skipped: Counter[str] = Counter()

    def locator(self, e: DXFGraphic, view: str, handle: str) -> SourceLocator:
        ext = bbox.extents([e])
        box = (ext.extmin.x, ext.extmin.y, ext.extmax.x, ext.extmax.y) if ext.has_data else None
        return SourceLocator(
            file_id=self.file_id,
            version=self.version,
            view=view,
            layer=e.dxf.get("layer"),
            handle=handle,
            bbox=box,
            confidence=1.0,
        )

    def visit(self, e: DXFGraphic, view: str, handle: str, origin: str | None = None) -> None:
        kind = e.dxftype()
        if kind in ("LWPOLYLINE", "POLYLINE", "INSERT"):
            part_origin = f"block {e.dxf.get('name')}" if kind == "INSERT" else kind
            for part in e.virtual_entities():  # type: ignore[attr-defined]
                self.visit(part, view, handle, origin=part_origin)
            for attrib in getattr(e, "attribs", []):  # INSERT attribute values, e.g. title-block fields
                self.visit(attrib, view, attrib.dxf.handle, origin=part_origin)
            return
        if kind == "ATTRIB":
            kind = "TEXT"
        if kind not in _KINDS:
            self.skipped[kind] += 1
            return
        loc = self.locator(e, view, handle)
        data: dict[str, Any] = {"from": origin} if origin else {}
        if kind == "DIMENSION":
            data |= self.dimension(e, loc)
        elif kind in ("TEXT", "MTEXT"):
            text = e.plain_text() if kind == "MTEXT" else e.dxf.text  # type: ignore[attr-defined]
            data["text"] = text
            self.texts.append(TextItem(text=text, locator=loc))
        else:
            data |= _geometry(e)
        self.entities.append(GeometryEntity(kind=_KINDS[kind], locator=loc, data=data))  # type: ignore[arg-type]

    def dimension(self, e: Any, loc: SourceLocator) -> dict[str, Any]:
        measured = float(e.get_measurement())
        displayed = _displayed_text(e)
        m = _NUMBER.search(displayed or "")
        value = float(m.group()) if m else None
        # Displayed text is rounded: allow half a unit of its last decimal place.
        rounding = 0.5 * 10 ** -_decimals(m.group()) if m else 0.0
        if value is not None and abs(value - measured) > rounding + MEASUREMENT_TOL:
            self.flags.append(
                Flag(
                    code="DIM_TEXT_MISMATCH",
                    target=loc,
                    message=f"dimension text {displayed!r} differs from measured {measured:g}",
                )
            )
        return {
            "dimtype": DIMTYPES.get(e.dimtype, str(e.dimtype)),
            "measurement": measured,
            "displayed": displayed,
            "value": value if value is not None else measured,
            **_measured_points(e),
            **_text_placement(e),
        }


def _strip_xdata(data: bytes) -> bytes:
    """Drop every XDATA tag (group codes 1000 to 1071) from an ASCII DXF."""
    lines = data.replace(b"\r\n", b"\n").split(b"\n")
    out: list[bytes] = []
    for i in range(0, len(lines) - 1, 2):
        code = lines[i].strip()
        if code.isdigit() and 1000 <= int(code) <= 1071:
            continue
        out += [lines[i], lines[i + 1]]
    return b"\n".join(out) + b"\n"


def _measured_points(e: Any) -> dict[str, Any]:
    """The points a DIMENSION measures, for association to features (Phase 2 task 2).

    DXF reference: linear and aligned use defpoint2 and defpoint3 (angle 0 = x axis,
    90 = y axis); diameter has defpoint and defpoint4 at opposite ends of the
    diameter; radius has defpoint at the centre and defpoint4 on the arc.
    """
    xy = lambda p: [float(p[0]), float(p[1])]  # noqa: E731
    kind = e.dimtype
    if kind in (0, 1):
        return {"p1": xy(e.dxf.defpoint2), "p2": xy(e.dxf.defpoint3), "angle": float(e.dxf.get("angle", 0.0))}
    if kind == 3:
        a, b = e.dxf.defpoint, e.dxf.defpoint4
        return {"center": [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]}
    if kind == 4:
        return {"center": xy(e.dxf.defpoint)}
    return {}


def _decimals(number: str) -> int:
    return len(number.split(".")[1]) if "." in number else 0


def _displayed_text(e: Any) -> str | None:
    override = (e.dxf.get("text") or "").strip()
    block = e.get_geometry_block()
    if block is not None:
        for part in block:
            if part.dxftype() == "MTEXT":
                return str(part.plain_text())
            if part.dxftype() == "TEXT":
                return str(part.dxf.text)
    return override if override not in ("", "<>") else None


def _text_placement(e: Any) -> dict[str, Any]:
    """Where the dimension text is drawn, and its height (from the rendered geometry block)."""
    block = e.get_geometry_block()
    for part in block or []:
        if part.dxftype() in ("MTEXT", "TEXT"):
            at = part.dxf.insert
            height = part.dxf.get("char_height" if part.dxftype() == "MTEXT" else "height")
            return {"text_at": [float(at[0]), float(at[1])], "text_height": float(height) if height else None}
    return {}


def _geometry(e: Any) -> dict[str, Any]:
    t = e.dxftype()
    if t == "LINE":
        return {"start": list(e.dxf.start)[:2], "end": list(e.dxf.end)[:2]}
    if t == "CIRCLE":
        return {"center": list(e.dxf.center)[:2], "radius": e.dxf.radius}
    if t == "ARC":
        return {
            "center": list(e.dxf.center)[:2],
            "radius": e.dxf.radius,
            "start_angle": e.dxf.start_angle,
            "end_angle": e.dxf.end_angle,
        }
    if t == "SPLINE":
        return {"control_points": [list(p)[:2] for p in e.control_points], "degree": e.dxf.degree}
    return {}


def parse(data: bytes, file_id: str, version: str) -> tuple[Geometry, list[Flag], dict[str, Any]]:
    """Parse DXF bytes into a ``geometry`` artifact, flags and metrics."""
    # recover.read takes raw bytes: it handles encodings, CRLF line endings and broken
    # structure, and reports what it fixed. ezdxf.read on a text stream returned an
    # empty document for CRLF files.
    r = _Reader(file_id, version)
    try:
        doc, auditor = recover.read(io.BytesIO(data))
    except const.DXFXDataError as exc:
        # Malformed extended data (XDATA) makes ezdxf reject the whole file. LibreDWG's
        # dwg2dxf writes such XDATA on dimensions. XDATA holds application settings, not
        # geometry, so drop it and read again.
        doc, auditor = recover.read(io.BytesIO(_strip_xdata(data)))
        r.flags.append(
            Flag(
                code="DXF_RECOVERED",
                severity="info",
                message=f"invalid extended data (XDATA) removed before reading: {exc}",
            )
        )
    if auditor.has_errors or auditor.has_fixes:
        r.flags.append(
            Flag(
                code="DXF_RECOVERED",
                severity="info",
                message=f"DXF structure repaired: {len(auditor.errors)} errors, {len(auditor.fixes)} fixes",
            )
        )
    views = []
    for layout in doc.layouts:
        entities = list(layout)
        if entities:
            views.append(layout.name)
        for e in entities:
            r.visit(e, layout.name, e.dxf.handle)
    # Dimensions the auditor removed (invalid geometry blocks) are read from their raw tags.
    seen = {e.locator.handle for e in r.entities}
    rescued = [d for d in raw_dimensions(data) if d["handle"] not in seen]
    for d in rescued:
        loc = SourceLocator(
            file_id=file_id,
            version=version,
            view="Model",
            layer=d.pop("layer"),
            handle=d.pop("handle"),
            bbox=d.pop("bbox"),
            confidence=1.0,
        )
        r.entities.append(GeometryEntity(kind="dimension", locator=loc, data=d))
    if rescued:
        r.flags.append(
            Flag(
                code="DXF_RECOVERED",
                severity="info",
                message=f"{len(rescued)} dimension(s) read from their own tags because their "
                "geometry blocks were invalid; displayed text not available",
            )
        )
    title, tb_flags = extract(r.texts)
    r.flags.extend(tb_flags)
    units = INSUNITS.get(doc.header.get("$INSUNITS", 0))
    stated = (
        _UNIT_WORDS.get(title.units.value.strip().lower())
        if title and title.units and title.units.value
        else None
    )
    if title and title.units and stated and units and stated != units:
        r.flags.append(
            Flag(
                code="UNIT_MISMATCH",
                target=title.units.locator,
                message=f"title block units {title.units.value!r}, DXF header units {units!r}",
            )
        )
    if r.skipped:
        r.flags.append(
            Flag(
                code="UNSUPPORTED_ENTITY",
                severity="info",
                message=f"entity types not in the geometry schema were skipped: {dict(r.skipped)}",
            )
        )
    geometry = Geometry(
        views=views,
        units=units,
        scale=title.scale.value if title and title.scale else None,
        entities=r.entities,
        title_block=title,
    )
    metrics = {
        "entities": len(r.entities),
        "dimensions": sum(1 for x in r.entities if x.kind == "dimension"),
        "skipped": dict(r.skipped),
    }
    return geometry, r.flags, metrics

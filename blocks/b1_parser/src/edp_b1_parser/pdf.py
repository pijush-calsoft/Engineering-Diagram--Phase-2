"""Vector PDF input with pypdfium2 (plan Phase 2, "Approach by input": vector PDF).

"pdfplumber / pypdfium2 for paths and text with coordinates; reconstruct lines, arcs and
text runs; map to drawing units from the title-block scale" (plan Phase 2).

- **Paths**: straight segments become lines. Runs of cubic Beziers become a circle when
  closed with points at one radius, otherwise an arc through their start, middle and end.
- **Text**: pdfium's text runs (one per line of text) become text entities. A run that is
  only a number, optionally with a diameter or radius sign, becomes a dimension value. A
  PDF has no dimension objects, so these dimensions carry no measured points: block 2 can
  link them to features by value only.
- **Units**: coordinates are read in points (1/72 in) and converted with the title block's
  units and scale. Without stated units they stay in points and the drawing is flagged.
- **Scans**: a page with images and no text is reported as a scan; scans go through the
  multimodal path (ADR-0007), which is not built yet (OD-43).

Locators: ``view`` is the page (``page-1``), ``handle`` is ``p<page>/path-<n>`` or
``p<page>/text-<n>``, ``bbox`` is in drawing units.
"""

import ctypes
import math
import re
from typing import Any

import pypdfium2 as pdfium
import pypdfium2.raw as raw

from edp_b1_parser.title_block import TextItem, extract
from edp_contracts import Flag, SourceLocator
from edp_contracts.artifacts.geometry import Geometry, GeometryEntity

PT_PER_UNIT = {"mm": 72 / 25.4, "cm": 72 / 2.54, "m": 72 / 0.0254, "in": 72.0, "ft": 864.0}
_UNIT_WORDS = {
    "mm": "mm",
    "millimetre": "mm",
    "millimetres": "mm",
    "millimeter": "mm",
    "millimeters": "mm",
    "cm": "cm",
    "m": "m",
    "in": "in",
    "inch": "in",
    "inches": "in",
    '"': "in",
    "ft": "ft",
}
_DIM_TEXT = re.compile(r"^\s*(?P<sign>Ø|ø|⌀|R)?\s*(?P<value>[+-]?\d*\.?\d+)\s*$")
_SCALE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)\s*$")
REL_TOL = 1e-3  # circle fit: points within 0.1 % of the mean radius


def _segments(obj: Any) -> list[list[tuple[int, tuple[float, float]]]]:
    """Subpaths of a path object as (segment type, point) lists, in page coordinates."""
    m = obj.get_matrix()
    subpaths: list[list[tuple[int, tuple[float, float]]]] = []
    x, y = ctypes.c_float(), ctypes.c_float()
    for j in range(raw.FPDFPath_CountSegments(obj.raw)):
        seg = raw.FPDFPath_GetPathSegment(obj.raw, j)
        raw.FPDFPathSegment_GetPoint(seg, ctypes.byref(x), ctypes.byref(y))
        kind = raw.FPDFPathSegment_GetType(seg)
        px, py = m.a * x.value + m.c * y.value + m.e, m.b * x.value + m.d * y.value + m.f
        if kind == raw.FPDF_SEGMENT_MOVETO or not subpaths:
            subpaths.append([])
        subpaths[-1].append((kind, (px, py)))
    return subpaths


def _circle_through(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]):  # noqa: ANN202
    d = 2 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]))
    if abs(d) < 1e-12:
        return None
    ux = (
        (a[0] ** 2 + a[1] ** 2) * (b[1] - c[1])
        + (b[0] ** 2 + b[1] ** 2) * (c[1] - a[1])
        + (c[0] ** 2 + c[1] ** 2) * (a[1] - b[1])
    ) / d
    uy = (
        (a[0] ** 2 + a[1] ** 2) * (c[0] - b[0])
        + (b[0] ** 2 + b[1] ** 2) * (a[0] - c[0])
        + (c[0] ** 2 + c[1] ** 2) * (b[0] - a[0])
    ) / d
    return (ux, uy), math.dist((ux, uy), a)


def _bezier_mid(seg: list[tuple[float, float]]) -> tuple[float, float]:
    """Point at t = 0.5 on a cubic Bezier (p0, c1, c2, p3)."""
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = seg
    return (x0 + 3 * x1 + 3 * x2 + x3) / 8, (y0 + 3 * y1 + 3 * y2 + y3) / 8


def _curve(points: list[tuple[float, float]], mid: tuple[float, float]) -> tuple[str, dict[str, Any]] | None:
    """Circle or arc from the on-curve points of a Bezier run (first point = start).

    ``mid`` is a point on the run's middle segment (t = 0.5), so a single-segment arc
    still has three distinct points to fit.
    """
    closed = math.dist(points[0], points[-1]) < 1e-6 * max(1.0, abs(points[0][0]), abs(points[0][1]))
    if closed and len(points) >= 5:
        ring = points[:-1]
        cx, cy = sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)
        radii = [math.dist((cx, cy), p) for p in ring]
        r = sum(radii) / len(radii)
        if r > 0 and max(abs(x - r) for x in radii) <= REL_TOL * r:
            return "circle", {"center": [cx, cy], "radius": r}
    fit = _circle_through(points[0], mid, points[-1])
    if fit is None:
        return None
    (cx, cy), r = fit
    ang = [math.degrees(math.atan2(p[1] - cy, p[0] - cx)) % 360 for p in (points[0], mid, points[-1])]
    ccw = (ang[1] - ang[0]) % 360 < (ang[2] - ang[0]) % 360
    start, end = (ang[0], ang[2]) if ccw else (ang[2], ang[0])
    return "arc", {"center": [cx, cy], "radius": r, "start_angle": start, "end_angle": end}


def _scale_factor(text: str | None) -> float:
    """Paper-to-real factor from a 'SCALE: a:b' value (1:2 means the drawing is half size)."""
    m = _SCALE.match(text or "")
    return float(m.group(2)) / float(m.group(1)) if m and float(m.group(1)) > 0 else 1.0


def parse(data: bytes, file_id: str, version: str) -> tuple[Geometry, list[Flag], dict[str, Any]]:
    doc = pdfium.PdfDocument(data)
    flags: list[Flag] = []
    raw_entities: list[tuple[str, dict[str, Any], str, str, tuple[float, float, float, float]]] = []
    texts_pt: list[tuple[str, str, str, tuple[float, float, float, float]]] = []
    views: list[str] = []
    images = 0
    for p_index in range(len(doc)):
        page = doc[p_index]
        view = f"page-{p_index + 1}"
        views.append(view)
        n_path = 0
        for obj in page.get_objects(max_depth=5):
            if obj.type == raw.FPDF_PAGEOBJ_IMAGE:
                images += 1
            if obj.type != raw.FPDF_PAGEOBJ_PATH:
                continue
            n_path += 1
            handle = f"p{p_index + 1}/path-{n_path}"
            for sub in _segments(obj):
                prev = sub[0][1]
                i = 1
                while i < len(sub):
                    kind, pt = sub[i]
                    if kind == raw.FPDF_SEGMENT_LINETO:
                        raw_entities.append(
                            ("line", {"start": list(prev), "end": list(pt)}, view, handle, _box([prev, pt]))
                        )
                        prev = pt
                        i += 1
                    elif kind == raw.FPDF_SEGMENT_BEZIERTO:
                        run = [prev]
                        segs = []
                        while i + 2 < len(sub) and sub[i][0] == raw.FPDF_SEGMENT_BEZIERTO:
                            segs.append([run[-1], sub[i][1], sub[i + 1][1], sub[i + 2][1]])
                            run.append(sub[i + 2][1])
                            i += 3
                        shape = _curve(run, _bezier_mid(segs[len(segs) // 2])) if segs else None
                        if shape:
                            raw_entities.append((shape[0], shape[1], view, handle, _box(run)))
                        prev = run[-1]
                    else:
                        i += 1
        tp = page.get_textpage()
        for rect_no in range(tp.count_rects()):
            rect = tp.get_rect(rect_no)
            value = tp.get_text_bounded(*rect).strip()
            if value:
                texts_pt.append((value, view, f"p{p_index + 1}/text-{rect_no + 1}", rect))
    if images and not texts_pt:
        flags.append(
            Flag(
                code="SCANNED_PDF",
                severity="review",
                message="PDF pages hold images but no text: scans need the multimodal path (ADR-0007, OD-43)",
            )
        )

    # Title block first (in points), to learn units and scale.
    def loc(view: str, handle: str, box: tuple[float, float, float, float], k: float) -> SourceLocator:
        return SourceLocator(
            file_id=file_id,
            version=version,
            view=view,
            handle=handle,
            bbox=(box[0] / k, box[1] / k, box[2] / k, box[3] / k),
            confidence=1.0,
        )

    title, tb_flags = extract([TextItem(text=t, locator=loc(v, h, b, 1.0)) for t, v, h, b in texts_pt])
    units = (
        _UNIT_WORDS.get(title.units.value.strip().lower())
        if title and title.units and title.units.value
        else None
    )
    if units is None:
        flags.append(
            Flag(
                code="UNIT_MISMATCH",
                message="[UNITS_UNKNOWN] the PDF states no units in its title block; "
                "coordinates stay in points",
            )
        )
    k = (
        PT_PER_UNIT[units] / _scale_factor(title.scale.value if title and title.scale else None)
        if units
        else 1.0
    )
    if title:  # re-express title-block locators in drawing units
        title, tb_flags = extract([TextItem(text=t, locator=loc(v, h, b, k)) for t, v, h, b in texts_pt])
    flags.extend(tb_flags)

    entities: list[GeometryEntity] = []
    for ent_kind, d, view, handle, box in raw_entities:
        entities.append(GeometryEntity(kind=ent_kind, locator=loc(view, handle, box, k), data=_scaled(d, k)))  # type: ignore[arg-type]
    n_dims = 0
    for text, view, handle, box in texts_pt:
        m = _DIM_TEXT.match(text)
        if m:
            n_dims += 1
            sign = m.group("sign")
            dimtype = "diameter" if sign and sign != "R" else "radius" if sign == "R" else "unspecified"
            centre = [(box[0] + box[2]) / 2 / k, (box[1] + box[3]) / 2 / k]
            dim_data = {
                "dimtype": dimtype,
                "displayed": text,
                "value": float(m.group("value")),
                "measurement": None,
                "text_at": centre,
                "text_height": (box[3] - box[1]) / k,
                "from_text": True,
            }
            entities.append(
                GeometryEntity(kind="dimension", locator=loc(view, handle, box, k), data=dim_data)
            )
        else:
            entities.append(
                GeometryEntity(kind="text", locator=loc(view, handle, box, k), data={"text": text})
            )
    geometry = Geometry(
        views=views,
        units=units,
        scale=title.scale.value if title and title.scale else None,
        entities=entities,
        title_block=title,
    )
    metrics = {"entities": len(entities), "dimensions": n_dims, "pages": len(views), "images": images}
    return geometry, flags, metrics


def _box(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _scaled(d: dict[str, Any], k: float) -> dict[str, Any]:
    out = dict(d)
    for key in ("start", "end", "center"):
        if key in out:
            out[key] = [out[key][0] / k, out[key][1] / k]
    if "radius" in out:
        out["radius"] = out["radius"] / k
    return out

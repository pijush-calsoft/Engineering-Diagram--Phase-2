"""Vector-PDF copies of a synthetic DXF set, for the PDF path of the parser (plan Phase 2).

Each drawing is written as a one-page vector PDF at its title-block scale (1:1): lines,
arcs and circles as PDF paths (curves as cubic Beziers), text in Helvetica. Dimensions are
drawn from their DXF geometry blocks, so the PDF holds what a CAD PDF export holds: lines,
arrows and text, no dimension objects.

A ``<id>.pdfmap.json`` sidecar records the page transform (``pt_per_unit``, ``offset_pt``)
and, per dimension handle, where its text sits in drawing units, so evaluation can place
ground-truth positions on the page. Written by hand (no
third-party PDF library), so the generator adds no dependency.
"""

import json
import math
import shutil
from pathlib import Path

import ezdxf
from ezdxf import bbox

from edp_eval.synth.labels import SyntheticLabel

PT_PER_UNIT = {"mm": 72 / 25.4, "in": 72.0}
MARGIN_PT = 36.0
KAPPA = 0.5522847498  # cubic Bezier circle constant
DIGIT_WIDTH_EM = 0.556  # Helvetica digit advance width


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


class _Page:
    def __init__(self, scale: float, ox: float, oy: float) -> None:
        self.s, self.ox, self.oy = scale, ox, oy
        self.ops: list[str] = []

    def xy(self, x: float, y: float) -> tuple[float, float]:
        return x * self.s + self.ox, y * self.s + self.oy

    def line(self, a, b) -> None:  # noqa: ANN001
        (x1, y1), (x2, y2) = self.xy(a[0], a[1]), self.xy(b[0], b[1])
        self.ops.append(f"{x1:.3f} {y1:.3f} m {x2:.3f} {y2:.3f} l S")

    def arc(self, cx: float, cy: float, r: float, a0: float, a1: float, closed: bool = False) -> None:
        sweep = (a1 - a0) % 360 or 360.0
        n = max(1, math.ceil(sweep / 90))
        step = math.radians(sweep / n)
        k = 4 / 3 * math.tan(step / 4)
        t = math.radians(a0)
        x0, y0 = self.xy(cx + r * math.cos(t), cy + r * math.sin(t))
        parts = [f"{x0:.3f} {y0:.3f} m"]
        for _ in range(n):
            t1 = t + step
            p1 = (cx + r * (math.cos(t) - k * math.sin(t)), cy + r * (math.sin(t) + k * math.cos(t)))
            p2 = (cx + r * (math.cos(t1) + k * math.sin(t1)), cy + r * (math.sin(t1) - k * math.cos(t1)))
            p3 = (cx + r * math.cos(t1), cy + r * math.sin(t1))
            q1, q2, q3 = self.xy(*p1), self.xy(*p2), self.xy(*p3)
            parts.append(f"{q1[0]:.3f} {q1[1]:.3f} {q2[0]:.3f} {q2[1]:.3f} {q3[0]:.3f} {q3[1]:.3f} c")
            t = t1
        self.ops.append(" ".join(parts) + (" h S" if closed else " S"))

    def text(self, value: str, x: float, y: float, height: float, rotation: float, centred: bool) -> None:
        size = height * self.s
        a = math.radians(rotation)
        if centred:  # MTEXT middle-centre: shift by half the (approximate) width and height
            w = DIGIT_WIDTH_EM * size * len(value)
            x -= (w / 2 * math.cos(a) - size / 2 * math.sin(a)) / self.s
            y -= (w / 2 * math.sin(a) + size / 2 * math.cos(a)) / self.s
        px, py = self.xy(x, y)
        c, s = math.cos(a), math.sin(a)
        body = _esc(value).encode("cp1252", errors="replace").decode("latin-1")
        self.ops.append(
            f"BT /F1 {size:.3f} Tf {c:.6f} {s:.6f} {-s:.6f} {c:.6f} {px:.3f} {py:.3f} Tm ({body}) Tj ET"
        )

    def entity(self, e) -> None:  # noqa: ANN001
        t = e.dxftype()
        if t == "LINE":
            self.line(e.dxf.start, e.dxf.end)
        elif t == "CIRCLE":
            self.arc(e.dxf.center[0], e.dxf.center[1], e.dxf.radius, 0, 360, closed=True)
        elif t == "ARC":
            self.arc(e.dxf.center[0], e.dxf.center[1], e.dxf.radius, e.dxf.start_angle, e.dxf.end_angle)
        elif t == "TEXT":
            self.text(
                e.dxf.text, e.dxf.insert[0], e.dxf.insert[1], e.dxf.height, e.dxf.get("rotation", 0), False
            )
        elif t == "MTEXT":
            self.text(
                e.plain_text(),
                e.dxf.insert[0],
                e.dxf.insert[1],
                e.dxf.char_height,
                e.dxf.get("rotation", 0),
                e.dxf.get("attachment_point", 1) == 5,
            )
        elif t in ("LWPOLYLINE", "POLYLINE", "INSERT", "DIMENSION"):
            for part in e.virtual_entities():
                self.entity(part)


def _pdf(ops: list[str], width: float, height: float) -> bytes:
    stream = "\n".join(["0 G 0.5 w 1 J 1 j"] + ops).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width:.3f} {height:.3f}] "
        f"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>".encode(),
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def write_pdf(dxf_path: Path, units: str, out_pdf: Path) -> dict:
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    ext = bbox.extents(msp)
    s = PT_PER_UNIT[units]
    ox, oy = MARGIN_PT - ext.extmin.x * s, MARGIN_PT - ext.extmin.y * s
    page = _Page(s, ox, oy)
    for e in msp:
        page.entity(e)
    width = (ext.extmax.x - ext.extmin.x) * s + 2 * MARGIN_PT
    height = (ext.extmax.y - ext.extmin.y) * s + 2 * MARGIN_PT
    out_pdf.write_bytes(_pdf(page.ops, width, height))
    texts: dict[str, list[float]] = {}
    for d in msp.query("DIMENSION"):
        for part in d.virtual_entities():  # type: ignore[attr-defined]  # DIMENSION entities have it
            if part.dxftype() == "MTEXT":
                texts[d.dxf.handle] = [part.dxf.insert[0], part.dxf.insert[1], part.dxf.char_height]
                break
    return {"pt_per_unit": s, "offset_pt": [ox, oy], "units": units, "dimension_text": texts}


def write_pdf_set(src: Path, out: Path) -> list[str]:
    """Write a vector PDF, its page-map sidecar and a copy of the labels for each drawing in ``src``."""
    out.mkdir(parents=True, exist_ok=True)
    ids = []
    for label_path in sorted(src.glob("*.labels.json")):
        label = SyntheticLabel.model_validate_json(label_path.read_text(encoding="utf-8"))
        mapping = write_pdf(src / f"{label.id}.dxf", label.units, out / f"{label.id}.pdf")
        (out / f"{label.id}.pdfmap.json").write_text(json.dumps(mapping), encoding="utf-8")
        shutil.copyfile(label_path, out / label_path.name)
        ids.append(label.id)
    return ids

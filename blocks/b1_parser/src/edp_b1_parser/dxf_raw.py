"""Read DIMENSION entities from raw DXF tags, without their geometry blocks.

ezdxf's auditor removes a DIMENSION whose geometry block is missing or invalid. LibreDWG
0.11's ``dwg2dxf`` writes such blocks (found in Phase 2), so a converted DWG would lose
every dimension. A DIMENSION's own tags still hold what the parser needs (DXF reference,
DIMENSION group codes):

| code | meaning |
|---|---|
| 5, 8 | handle, layer |
| 70 | dimension type (low 3 bits: 0 linear, 1 aligned, 3 diameter, 4 radius) |
| 1 | text override ("" or "<>" means the measurement is shown) |
| 10/20 | definition point (diameter: one end; radius: centre) |
| 11/21 | text middle point |
| 13/23, 14/24 | linear and aligned: the two measured points |
| 15/25 | diameter: other end; radius: point on the arc |
| 42 | actual measurement (optional) |
| 50 | linear: rotation angle |
"""

import math
import re
from typing import Any

_NUMBER = re.compile(r"[-+]?\d*\.?\d+")


def _pairs(data: bytes) -> list[tuple[int, str]]:
    lines = data.decode("utf-8", errors="replace").replace("\r\n", "\n").split("\n")
    out = []
    for i in range(0, len(lines) - 1, 2):
        code = lines[i].strip()
        if code.lstrip("-").isdigit():
            out.append((int(code), lines[i + 1].strip()))
    return out


def raw_dimensions(data: bytes) -> list[dict[str, Any]]:
    """Every DIMENSION in the ENTITIES section, as plain values."""
    tags = _pairs(data)
    in_entities = False
    current: dict[int, str] | None = None
    dims: list[dict[int, str]] = []
    for code, value in tags:
        if code == 2 and value == "ENTITIES":
            in_entities = True
        elif code == 0 and value == "ENDSEC":
            in_entities = False
        if not in_entities:
            continue
        if code == 0:
            if current is not None:
                dims.append(current)
            current = {} if value == "DIMENSION" else None
            continue
        if current is not None and code not in current:  # first occurrence: the entity's own tag
            current[code] = value
    if current is not None:
        dims.append(current)
    return [d for d in (_dimension(t) for t in dims) if d]


def _pt(t: dict[int, str], x: int) -> list[float] | None:
    try:
        return [float(t[x]), float(t[x + 10])]
    except (KeyError, ValueError):
        return None


def _dimension(t: dict[int, str]) -> dict[str, Any] | None:
    handle = t.get(5)
    kind = int(t.get(70, "0")) & 7
    if not handle or kind not in (0, 1, 3, 4):
        return None
    out: dict[str, Any] = {"handle": handle, "layer": t.get(8)}
    p10, p11, p13, p14, p15 = _pt(t, 10), _pt(t, 11), _pt(t, 13), _pt(t, 14), _pt(t, 15)
    if kind in (0, 1):
        if not (p13 and p14):
            return None
        angle = float(t.get(50, "0") or 0)
        if kind == 0:
            a = math.radians(angle)
            measured = abs((p14[0] - p13[0]) * math.cos(a) + (p14[1] - p13[1]) * math.sin(a))
        else:
            measured = math.dist(p13, p14)
        out |= {"dimtype": "linear" if kind == 0 else "aligned", "p1": p13, "p2": p14, "angle": angle}
        points = [p13, p14]
    else:
        if not (p10 and p15):
            return None
        if kind == 3:
            measured = math.dist(p10, p15)
            out |= {"dimtype": "diameter", "center": [(p10[0] + p15[0]) / 2, (p10[1] + p15[1]) / 2]}
        else:
            measured = math.dist(p10, p15)
            out |= {"dimtype": "radius", "center": p10}
        points = [p10, p15]
    if 42 in t:
        try:
            stored = float(t[42])
            if stored > 0:
                measured = stored
        except ValueError:
            pass
    text = t.get(1, "")
    displayed = None if text in ("", "<>") else text.replace("<>", f"{measured:g}")
    m = _NUMBER.search(displayed or "")
    out |= {
        "measurement": measured,
        "displayed": displayed,
        "value": float(m.group()) if m else measured,
        "text_at": p11,
        "text_height": None,
        "recovered": True,
    }
    if p11:
        points.append(p11)
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    out["bbox"] = (min(xs), min(ys), max(xs), max(ys))
    return out


def entity_handles(data: bytes) -> set[str]:
    """Handles (group code 5) of every entity in the file, read from raw tags."""
    tags = _pairs(data)
    out, after_entity_start = set(), False
    for code, value in tags:
        if code == 0:
            after_entity_start = True
        elif code == 5 and after_entity_start:
            out.add(value)
            after_entity_start = False
    return out

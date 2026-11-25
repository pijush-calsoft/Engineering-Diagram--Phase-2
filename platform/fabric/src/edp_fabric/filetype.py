"""Detect the real file type from content (plan Phase 1 "type check"; deck slide 42).

Deck slide 42: "Type from content; extension is a hint, a mismatch gives a
warning" and "Unsupported type fails with unsupported_type, never a guess".
Kinds follow the R1 inputs (plan §2.1). A PDF is reported as ``pdf``; vector or
scanned is decided later by the Drawing Parser.
"""

from pathlib import PurePath
from typing import Literal

from pydantic import BaseModel

FileKind = Literal["dxf", "dwg", "pdf", "image", "step", "iges", "stl"]

_EXTENSIONS: dict[str, FileKind] = {
    ".dxf": "dxf",
    ".dwg": "dwg",
    ".pdf": "pdf",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".tif": "image",
    ".tiff": "image",
    ".step": "step",
    ".stp": "step",
    ".iges": "iges",
    ".igs": "iges",
    ".stl": "stl",
}


class UnsupportedTypeError(ValueError):
    code = "unsupported_type"


class Detection(BaseModel):
    kind: FileKind
    warning: str | None = None  # set when the extension disagrees with the content


def _from_content(data: bytes) -> FileKind | None:
    head = data[:512]
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"II*\x00", b"MM\x00*")):
        return "image"
    if head.startswith(b"AC10"):
        return "dwg"
    if head.startswith(b"AutoCAD Binary DXF"):
        return "dxf"
    text = head.decode("latin-1")
    lines = [ln.strip() for ln in text.splitlines()[:4]]
    if lines[:2] == ["0", "SECTION"] or (len(lines) >= 4 and lines[:4] == ["999", lines[1], "0", "SECTION"]):
        return "dxf"
    if text.lstrip().startswith("ISO-10303-21;"):
        return "step"
    first = text.splitlines()[0] if text else ""
    if len(first) >= 73 and first[72] == "S":  # IGES: start section flag in column 73
        return "iges"
    if text.lstrip().lower().startswith("solid") and b"facet" in data[:4096]:
        return "stl"
    if len(data) >= 84:  # binary STL: 80-byte header, count, 50 bytes per facet
        count = int.from_bytes(data[80:84], "little")
        if count and len(data) == 84 + 50 * count:
            return "stl"
    return None


def detect(data: bytes, filename: str) -> Detection:
    kind = _from_content(data)
    if kind is None:
        raise UnsupportedTypeError(f"unsupported_type: content of {filename!r} matches no supported format")
    hinted = _EXTENSIONS.get(PurePath(filename).suffix.lower())
    warning = None if hinted in (None, kind) else f"extension suggests {hinted}, content is {kind}"
    return Detection(kind=kind, warning=warning)

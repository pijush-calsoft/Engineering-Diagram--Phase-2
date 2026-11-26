"""Check that a 2D drawing gave the parser something to read (OD-62, added 2026-11-26).

Some tools write a drawing's lettering and dimensions as outlines: filled HATCH glyphs and
plain lines instead of TEXT and DIMENSION entities. Such a file passes a DXF audit, and the
parser reads its lines, but no value, dimension or title-block field. Without a flag the run
goes on with an empty design graph as if all were well (plan principle: flag, never guess).

A 2D drawing with no dimension entity is flagged for review. 3D models (STEP, IGES, STL) carry
no dimensions and are not checked.
"""

from collections.abc import Mapping

from edp_contracts import Flag
from edp_contracts.artifacts.geometry import Geometry

DRAWING_KINDS = frozenset({"dxf", "dwg", "pdf", "image"})


def annotation_flags(geometry: Geometry, kind: str, skipped: Mapping[str, int] | None = None) -> list[Flag]:
    """A review flag when a 2D drawing has no dimension entity; none otherwise."""
    if kind not in DRAWING_KINDS:
        return []
    counts = {k: 0 for k in ("dimension", "text")}
    for e in geometry.entities:
        if e.kind in counts:
            counts[e.kind] += 1
    if counts["dimension"]:
        return []
    shapes = len(geometry.entities) - counts["text"]
    if not geometry.entities:
        return [
            Flag(
                code="EMPTY_DRAWING",
                severity="review",
                message=f"no entities were read from the {kind.upper()} file",
            )
        ]
    if counts["text"]:
        hint = (
            f"{counts['text']} text item(s) were read; values written as plain text are not "
            "taken as dimensions"
        )
    else:
        hatches = (skipped or {}).get("HATCH", 0)
        hint = "no text either: lettering and dimensions are probably drawn as outlines"
        if hatches:
            hint += f" ({hatches} HATCH entities skipped)"
        hint += (
            ". Export the drawing again with text and dimensions kept as entities, or read it "
            "as a scan (ADR-0007)"
        )
    return [
        Flag(
            code="NO_DIMENSIONS",
            severity="review",
            message=f"{shapes} geometry entities but no dimension entity; {hint}",
        )
    ]

"""Construction domain: synthetic steel column base plates (owner direction 2026-11-26).

The team works on construction drawings. A column base plate is the simplest construction
steel part that runs the whole R1 loop the deck describes (deck slides 10, 19, 85): drawing,
interpretation, editable model, solver, margin, report. It is drawn with the same writer as
the generic ``plate`` family (two views, real DIMENSION entities, title block), so blocks 1 and
2 read it unchanged.

Where the numbers come from:

- Anchor-bolt sizes M16 to M30 and normal round clearance holes: bolt diameter + 2 mm up to
  M24, + 3 mm from M27 (EN 1090-2, normal round holes). Standard values, not plan values.
- Edge distance at least 1.2 d0 and spacing at least 2.2 d0 (EN 1993-1-8, minimum end and
  edge distances and spacings). The sampler rejects any draw that breaks them.
- Steel grades S275JR, S355JR, S355J2 (EN 10025-2 designations).
- Plate sizes, thicknesses and insets are generator settings in millimetres, not plan or deck
  values (same rule as ``parts.py``).

Only the ISO profile is used: construction drawings here are metric.
"""

import json
import random
from pathlib import Path

from edp_eval.golden import GoldenManifest
from edp_eval.synth.parts import Family, Hole, Plate
from edp_eval.synth.profiles import PROFILES

FAMILY: Family = "base_plate"
# Anchor bolt nominal diameter -> normal round clearance hole d0 (EN 1090-2).
ANCHOR_HOLES: dict[str, float] = {"M16": 18.0, "M20": 22.0, "M24": 26.0, "M27": 30.0, "M30": 33.0}
STEEL_GRADES = ("S275JR", "S355JR", "S355J2")
THICKNESSES = (15.0, 20.0, 25.0, 30.0, 40.0)
EDGE_FACTOR = 1.2  # e >= 1.2 d0 (EN 1993-1-8)
SPACING_FACTOR = 2.2  # p >= 2.2 d0 (EN 1993-1-8)


class Reject(ValueError):
    """A sampled plate breaks a detailing rule."""


def anchor_size(d0: float) -> str:
    return next(name for name, hole in ANCHOR_HOLES.items() if hole == d0)


def check_detailing(plate: Plate) -> None:
    """Raise ``Reject`` if a hole is closer to an edge than 1.2 d0 or to another hole than 2.2 d0."""
    for h in plate.holes:
        edge = min(h.x, h.y, plate.length - h.x, plate.width - h.y)
        if edge < EDGE_FACTOR * h.diameter:
            raise Reject(f"edge distance {edge:g} < {EDGE_FACTOR} d0 for d0 {h.diameter:g}")
    for i, a in enumerate(plate.holes):
        for b in plate.holes[i + 1 :]:
            gap = ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5
            if gap < SPACING_FACTOR * max(a.diameter, b.diameter):
                raise Reject(f"hole spacing {gap:g} < {SPACING_FACTOR} d0")


def sample_base_plate(rng: random.Random) -> Plate:
    """A rectangular base plate with four corner anchor holes, or six on long plates."""
    for _ in range(50):
        length = float(rng.randrange(250, 610, 10))
        width = float(rng.randrange(250, min(int(length), 600) + 10, 10))
        thickness = rng.choice(THICKNESSES)
        d0 = ANCHOR_HOLES[rng.choice(tuple(ANCHOR_HOLES))]
        inset = float(rng.randrange(40, 105, 5))
        xs = [inset, length - inset]
        if length >= 450 and rng.random() < 0.5:
            xs.insert(1, length / 2)
        holes = tuple(Hole(x, y, d0) for y in (inset, width - inset) for x in xs)
        plate = Plate(length, width, thickness, holes)
        try:
            check_detailing(plate)
        except Reject:
            continue
        return plate
    raise RuntimeError("no base plate satisfied the detailing rules in 50 draws")


def write_construction_set(out_dir: Path, count: int, seed: int, uri_prefix: str) -> GoldenManifest:
    """Write ``count`` base-plate drawings (ISO profile), labels and a manifest."""
    from edp_eval.synth import _item, _save  # shared writer helpers
    from edp_eval.synth.dxf_writer import generate

    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = uri_prefix.rstrip("/")
    profile = PROFILES["iso"]
    items = []
    for i in range(count):
        rng = random.Random(f"{seed}-construction-{i}")
        part = sample_base_plate(rng)
        title = {"part_number": f"EDP-BP-{i:04d}", "material": rng.choice(STEEL_GRADES)}
        doc, label = generate(profile, FAMILY, i, seed, part=part, title=title)
        label = label.model_copy(update={"id": f"con-iso-{FAMILY}-{i:03d}"})
        _save(out_dir, doc, label)
        items.append(_item(label.id, FAMILY, prefix))
    manifest = GoldenManifest(version=f"construction-seed{seed}-n{count}", items=items)
    (out_dir / "manifest.json").write_text(json.dumps(manifest.model_dump(), indent=2), encoding="utf-8")
    return manifest

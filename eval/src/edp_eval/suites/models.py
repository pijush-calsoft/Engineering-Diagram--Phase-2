"""3D input evaluation: STEP and STL against the synthetic model set (plan Phase 2, §7 Parser row).

Plan Phase 2 sets exit targets for vector DXF/PDF and scans only; how STEP, IGES and STL
are scored is open (TBD-AC-1 in docs/requirements/acceptance-criteria.md). This suite
reports, without targets:

- STEP: hole recall and precision (diameter and centre within ``value_tol``), largest
  bounding-box error, largest relative volume error, share of holes with an entity-id locator.
- STL: share of watertight meshes, share with the right through-opening hint, largest
  bounding-box error.

Usage: ``uv run python -m edp_eval.suites.models --golden DIR --value-tol T [--out FILE]``
"""

import argparse
import json
from pathlib import Path

from edp_b1_parser.model3d import parse_brep, parse_stl
from edp_eval.synth.models import ModelLabel


def run(golden: Path, value_tol: float) -> dict:
    labels = [
        ModelLabel.model_validate_json(p.read_text(encoding="utf-8"))
        for p in sorted(golden.glob("*.model.json"))
    ]
    if not labels:
        raise ValueError(f"no *.model.json in {golden}")
    tp = n_pred = n_truth = located = 0
    bbox_err = vol_err = stl_bbox_err = 0.0
    watertight = hint_ok = 0
    for lb in labels:
        solid = parse_brep((golden / f"{lb.id}.step").read_bytes(), "step", lb.id, "golden")[0].solids[0]
        pred = [(h.diameter, h.axis_origin[0], h.axis_origin[1]) for h in solid.holes]
        n_pred += len(pred)
        n_truth += len(lb.holes)
        used: set[int] = set()
        for t in lb.holes:
            for i, (d, x, y) in enumerate(pred):
                if i not in used and all(
                    abs(a - b) <= value_tol for a, b in ((d, t.diameter), (x, t.x), (y, t.y))
                ):
                    used.add(i)
                    break
        tp += len(used)
        located += sum(1 for h in solid.holes if h.locators and all(loc.handle for loc in h.locators))
        bbox_err = max(bbox_err, max(abs(a - b) for a, b in zip(solid.bbox, lb.bbox, strict=True)))
        vol_err = max(vol_err, abs((solid.volume or 0) - lb.volume) / lb.volume)
        mesh = parse_stl((golden / f"{lb.id}.stl").read_bytes(), lb.id, "golden")[0].solids[0]
        watertight += bool(mesh.watertight)
        hint_ok += mesh.through_holes_hint == lb.through_openings
        stl_bbox_err = max(stl_bbox_err, max(abs(a - b) for a, b in zip(mesh.bbox, lb.bbox, strict=True)))
    n = len(labels)
    return {
        "golden": str(golden),
        "models": n,
        "settings": {"value_tol_mm": value_tol},
        "step": {
            "hole_recall": tp / n_truth if n_truth else 1.0,
            "hole_precision": tp / n_pred if n_pred else 1.0,
            "holes_with_entity_locator": located / n_pred if n_pred else 1.0,
            "max_bbox_error_mm": bbox_err,
            "max_volume_rel_error": vol_err,
        },
        "stl": {
            "watertight_share": watertight / n,
            "through_opening_hint_correct": hint_ok / n,
            "max_bbox_error_mm": stl_bbox_err,
        },
        "targets": "none in plan for 3D inputs (TBD-AC-1)",
    }


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m edp_eval.suites.models", description=__doc__)
    ap.add_argument("--golden", type=Path, required=True)
    ap.add_argument("--value-tol", type=float, required=True, help="mm; no default: not set by the plan")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    text = json.dumps(run(args.golden, args.value_tol), indent=2)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()

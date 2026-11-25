"""Drawing Parser evaluation on the DXF golden set (plan §7 Parser row, Phase 2 exit criteria).

Metrics per plan Phase 2: dimension value and target F1, title-block field
accuracy, entities with a valid source locator, calibration error (ECE).

Definitions used here (open items, recorded in eval/README.md):
- Dimension target: the DIMENSION entity handle, until dimension-to-feature
  association (Phase 2 task 2) is built. Then the target becomes the measured feature.
- Valid locator: the handle resolves to an entity in the same DXF file (TBD-AC-2).
- ECE items: every predicted dimension (correct = matched) and every truth
  title-block field (correct = exact match), with the parser's confidence.

Usage: ``uv run python -m edp_eval.suites.parser_dxf --golden DIR --value-tol T --n-bins N [--out FILE]``
"""

import argparse
import hashlib
import io
import json
from pathlib import Path

from ezdxf import recover
from pydantic import BaseModel

from edp_b1_parser import dxf
from edp_eval.metrics import PHASE2_TARGETS, Dimension, dimension_f1, expected_calibration_error
from edp_eval.synth.labels import SyntheticLabel


class Counts(BaseModel):
    drawings: int = 0
    tp: int = 0
    n_pred: int = 0
    n_truth: int = 0
    tb_correct: int = 0
    tb_total: int = 0
    loc_valid: int = 0
    loc_total: int = 0
    confidences: list[float] = []
    correct: list[bool] = []

    def add(self, other: "Counts") -> None:
        for k in ("drawings", "tp", "n_pred", "n_truth", "tb_correct", "tb_total", "loc_valid", "loc_total"):
            setattr(self, k, getattr(self, k) + getattr(other, k))
        self.confidences += other.confidences
        self.correct += other.correct

    def scores(self, n_bins: int) -> dict[str, float]:
        p = self.tp / self.n_pred if self.n_pred else 0.0
        r = self.tp / self.n_truth if self.n_truth else 0.0
        return {
            "dimension_f1": 2 * p * r / (p + r) if p + r else 0.0,
            "title_block_accuracy": self.tb_correct / self.tb_total if self.tb_total else 0.0,
            "locator_coverage": self.loc_valid / self.loc_total if self.loc_total else 0.0,
            "ece": expected_calibration_error(self.confidences, self.correct, n_bins),
        }


def evaluate_drawing(dxf_path: Path, label: SyntheticLabel, value_tol: float) -> Counts:
    data = dxf_path.read_bytes()
    geometry, _, _ = dxf.parse(data, hashlib.sha256(data).hexdigest(), "golden")
    c = Counts(drawings=1)

    dims = [e for e in geometry.entities if e.kind == "dimension"]
    pred = [Dimension(target=e.locator.handle or "", value=e.data["value"]) for e in dims]
    truth = [Dimension(target=d.handle, value=d.value) for d in label.dimensions]
    prf = dimension_f1(pred, truth, value_tol=value_tol)
    c.tp, c.n_pred, c.n_truth = prf.true_positives, prf.n_predicted, prf.n_truth
    truth_by_handle = {d.handle: d.value for d in label.dimensions}
    for e in dims:
        expected = truth_by_handle.get(e.locator.handle or "")
        c.confidences.append(e.locator.confidence)
        c.correct.append(expected is not None and abs(e.data["value"] - expected) <= value_tol)

    tb = geometry.title_block
    for key, field in label.title_block.items():
        got = getattr(tb, key) if tb else None
        ok = got is not None and got.value is not None and got.value.strip() == field.value.strip()
        c.tb_total += 1
        c.tb_correct += ok
        c.confidences.append(got.locator.confidence if got else 0.0)
        c.correct.append(ok)

    doc, _ = recover.read(io.BytesIO(data))
    c.loc_total = len(geometry.entities)
    c.loc_valid = sum(1 for e in geometry.entities if e.locator.handle and e.locator.handle in doc.entitydb)
    return c


def run(golden: Path, value_tol: float, n_bins: int) -> dict:
    groups: dict[str, Counts] = {}
    total = Counts()
    for label_path in sorted(golden.glob("*.labels.json")):
        label = SyntheticLabel.model_validate_json(label_path.read_text(encoding="utf-8"))
        c = evaluate_drawing(golden / f"{label.id}.dxf", label, value_tol)
        groups.setdefault(f"{label.profile}/{label.family}", Counts()).add(c)
        total.add(c)
    if not total.drawings:
        raise ValueError(f"no *.labels.json in {golden}")
    overall = total.scores(n_bins)
    return {
        "golden": str(golden),
        "drawings": total.drawings,
        "settings": {
            "value_tol": value_tol,
            "n_bins": n_bins,
            "dimension_target": "DIMENSION entity handle (association pending, Phase 2 task 2)",
        },
        "overall": overall,
        "targets_met_vector": {k: PHASE2_TARGETS[k].met(v, "vector") for k, v in overall.items()},
        "by_group": {g: c.scores(n_bins) | {"drawings": c.drawings} for g, c in sorted(groups.items())},
    }


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m edp_eval.suites.parser_dxf", description=__doc__)
    ap.add_argument("--golden", type=Path, required=True)
    ap.add_argument("--value-tol", type=float, required=True, help="no default: not set by the plan")
    ap.add_argument("--n-bins", type=int, required=True, help="no default: not set by the plan")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    report = run(args.golden, args.value_tol, args.n_bins)
    text = json.dumps(report, indent=2)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()

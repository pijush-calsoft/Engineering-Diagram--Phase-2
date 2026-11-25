"""Drawing Parser evaluation on the DXF golden set (plan §7 Parser row, Phase 2 exit criteria).

Metrics per plan Phase 2: dimension value and target F1, title-block field
accuracy, entities with a valid source locator, calibration error (ECE).

Definitions used here (open items, recorded in eval/README.md):
- Dimension target: the DIMENSION entity handle, until dimension-to-feature
  association (Phase 2 task 2) is built. Then the target becomes the measured feature.
- Valid locator: the handle belongs to an entity in the same file (TBD-AC-2). DWG files are
  converted by LibreDWG first and scored on the converted DXF. PDF has no handles: a
  locator is valid when it names its page object and has a bounding box, and dimensions
  are matched by value and position (within two text heights).
- ECE items: every predicted dimension (correct = matched) and every truth
  title-block field (correct = exact match), with the parser's confidence.

Usage: ``uv run python -m edp_eval.suites.parser_dxf --golden DIR --value-tol T --n-bins N [--out FILE]``
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

from pydantic import BaseModel

from edp_b1_parser import dwg, dxf, pdf
from edp_b1_parser.dxf_raw import entity_handles
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


def _pdf_targets(pdf_path: Path, label: SyntheticLabel) -> list[Dimension]:
    """Truth dimensions placed on the PDF page, in the parser's drawing units (sidecar ``.pdfmap.json``)."""
    mapping = json.loads(pdf_path.with_suffix(".pdfmap.json").read_text(encoding="utf-8"))
    ox, oy = (o / mapping["pt_per_unit"] for o in mapping["offset_pt"])
    out = []
    for d in label.dimensions:
        x, y, h = mapping["dimension_text"][d.handle]
        out.append(Dimension(target=f"{x + ox},{y + oy},{h}", value=d.value))
    return out


def _match_by_position(pred: list, truth: list[Dimension], value_tol: float) -> tuple[int, list[bool]]:
    """Greedy one-to-one match: same value, text within two text heights. Returns (TP, hits)."""
    used: set[int] = set()
    correct = []
    for e in pred:
        hit = None
        for i, t in enumerate(truth):
            x, y, h = (float(v) for v in t.target.split(","))
            if (
                i not in used
                and abs(e.data["value"] - t.value) <= value_tol
                and math.dist(e.data["text_at"], (x, y)) <= 2 * h
            ):
                hit = i
                break
        if hit is not None:
            used.add(hit)
        correct.append(hit is not None)
    return len(used), correct


def evaluate_drawing(dxf_path: Path, label: SyntheticLabel, value_tol: float) -> Counts:
    """Score one drawing. DWG goes through LibreDWG first; PDF goes through the PDF path.

    A PDF has no entity handles, so a predicted dimension is right when its value matches a
    truth dimension whose text was drawn within two text heights of it.
    """
    data = dxf_path.read_bytes()
    file_id = hashlib.sha256(data).hexdigest()
    suffix = dxf_path.suffix.lower()
    if suffix == ".pdf":
        geometry, _, _ = pdf.parse(data, file_id, "golden")
    else:
        if suffix == ".dwg":
            data, _ = dwg.convert(data)
        geometry, _, _ = dxf.parse(data, file_id, "golden")
    c = Counts(drawings=1)

    dims = [e for e in geometry.entities if e.kind == "dimension"]
    if suffix == ".pdf":
        truth_pdf = _pdf_targets(dxf_path, label)
        c.tp, correct = _match_by_position(dims, truth_pdf, value_tol)
        c.n_pred, c.n_truth = len(dims), len(truth_pdf)
        for e, ok in zip(dims, correct, strict=True):
            c.confidences.append(e.locator.confidence)
            c.correct.append(ok)
    else:
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

    c.loc_total = len(geometry.entities)
    if suffix == ".pdf":  # PDF locators: page object handles with a bounding box (TBD-AC-2)
        c.loc_valid = sum(1 for e in geometry.entities if e.locator.handle and e.locator.bbox)
    else:
        handles = entity_handles(data)
        c.loc_valid = sum(1 for e in geometry.entities if e.locator.handle and e.locator.handle in handles)
    return c


def run(golden: Path, value_tol: float, n_bins: int) -> dict:
    groups: dict[str, Counts] = {}
    total = Counts()
    for label_path in sorted(golden.glob("*.labels.json")):
        label = SyntheticLabel.model_validate_json(label_path.read_text(encoding="utf-8"))
        path = next(
            (
                golden / f"{label.id}{ext}"
                for ext in (".dxf", ".dwg", ".pdf")
                if (golden / f"{label.id}{ext}").is_file()
            ),
            golden / f"{label.id}.dxf",
        )
        c = evaluate_drawing(path, label, value_tol)
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

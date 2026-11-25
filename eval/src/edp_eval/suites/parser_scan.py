"""Drawing Parser evaluation on scans (plan §7 Parser row, Phase 2 exit criteria, "Scans" column).

Each scan is read through the Model Gateway, so a run costs money; ``--limit K`` scores K drawings
spread evenly over the sorted set (so every profile and family is sampled). Scoring follows the
PDF rules in ``parser_dxf``: a predicted dimension is right
when its value matches a truth dimension whose text lies within two text heights of the
predicted box centre (``.scanmap.json`` gives truth positions in image pixels, y up). A locator
is valid when it names its page object and has a box. Title-block fields must match exactly
after ``strip()``; a case-insensitive rate is reported beside it for information.

Usage: ``uv run python -m edp_eval.suites.parser_scan --golden DIR --value-tol T --n-bins N
[--limit K] [--out FILE]``
"""

import argparse
import hashlib
import json
from pathlib import Path

from edp_b1_parser import scan
from edp_eval.metrics import PHASE2_TARGETS, Dimension
from edp_eval.suites.parser_dxf import Counts, _match_by_position
from edp_eval.synth.labels import SyntheticLabel
from edp_gateway import Gateway, GatewayConfig


def evaluate_scan(
    path: Path, label: SyntheticLabel, value_tol: float, gateway: Gateway
) -> tuple[Counts, dict]:
    data = path.read_bytes()
    geometry, flags, metrics = scan.parse(
        data,
        "image",
        hashlib.sha256(data).hexdigest(),
        "golden",
        gateway,
        "synthetic",
        run_id=f"eval-{label.id}",
    )
    mapping = json.loads(path.with_suffix(".scanmap.json").read_text(encoding="utf-8"))
    truth = [
        Dimension(target=",".join(str(v) for v in mapping["dimension_text"][d.handle]), value=d.value)
        for d in label.dimensions
    ]
    c = Counts(drawings=1)
    dims = [e for e in geometry.entities if e.kind == "dimension" and e.data.get("text_at")]
    c.tp, correct = _match_by_position(dims, truth, value_tol)
    c.n_pred = len([e for e in geometry.entities if e.kind == "dimension"])
    c.n_truth = len(truth)
    for e, ok in zip(dims, correct, strict=True):
        c.confidences.append(e.locator.confidence)
        c.correct.append(ok)
    casefold = 0
    tb = geometry.title_block
    for key, field in label.title_block.items():
        got = getattr(tb, key) if tb else None
        ok = got is not None and got.value is not None and got.value.strip() == field.value.strip()
        casefold += (
            got is not None
            and got.value is not None
            and got.value.strip().casefold() == field.value.strip().casefold()
        )
        c.tb_total += 1
        c.tb_correct += ok
        c.confidences.append(got.locator.confidence if got else 0.0)
        c.correct.append(ok)
    c.loc_total = len(geometry.entities)
    c.loc_valid = sum(1 for e in geometry.entities if e.locator.handle and e.locator.bbox)
    detail = {
        "id": label.id,
        "dimensions": {"truth": c.n_truth, "predicted": c.n_pred, "matched": c.tp},
        "title_block": {"exact": c.tb_correct, "casefold": casefold, "fields": c.tb_total},
        "flags": sorted({f.code for f in flags}),
        "cost_usd": metrics.get("cost_usd"),
        "skew_found_deg": metrics["pages"][0]["skew_deg"],
        "skew_true_deg": round(mapping["skew_deg"], 3),
    }
    return c, detail


def run(golden: Path, value_tol: float, n_bins: int, limit: int | None, gateway: Gateway) -> dict:
    labels = sorted(golden.glob("*.labels.json"))
    if limit and limit < len(labels):
        labels = [labels[round(i * len(labels) / limit)] for i in range(limit)]
    if not labels:
        raise ValueError(f"no *.labels.json in {golden}")
    total = Counts()
    details = []
    for label_path in labels:
        label = SyntheticLabel.model_validate_json(label_path.read_text(encoding="utf-8"))
        c, d = evaluate_scan(golden / f"{label.id}.png", label, value_tol, gateway)
        total.add(c)
        details.append(d)
        print(json.dumps(d), flush=True)
    overall = total.scores(n_bins)
    tb_casefold = sum(d["title_block"]["casefold"] for d in details) / max(total.tb_total, 1)
    return {
        "golden": str(golden),
        "drawings": total.drawings,
        "settings": {"value_tol": value_tol, "n_bins": n_bins, "limit": limit, "match": "value and position"},
        "overall": overall | {"title_block_accuracy_casefold": tb_casefold},
        "targets_met_scans": {k: PHASE2_TARGETS[k].met(v, "scan") for k, v in overall.items()},
        "cost_usd": round(sum(d["cost_usd"] or 0 for d in details), 6),
        "drawings_detail": details,
    }


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m edp_eval.suites.parser_scan", description=__doc__)
    ap.add_argument("--golden", type=Path, required=True)
    ap.add_argument("--value-tol", type=float, required=True, help="no default: not set by the plan")
    ap.add_argument("--n-bins", type=int, required=True, help="no default: not set by the plan")
    ap.add_argument(
        "--limit", type=int, help="score K drawings spread over the set (each costs a model call)"
    )
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    report = run(args.golden, args.value_tol, args.n_bins, args.limit, Gateway(GatewayConfig.load()))
    text = json.dumps(report, indent=2)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()

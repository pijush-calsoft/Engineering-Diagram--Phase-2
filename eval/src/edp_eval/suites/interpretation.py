"""Interpretation evaluation on the golden set (plan §7 "Interpretation, KG" row, Phase 3 exit criteria).

- **Feature match**: plan Phase 3 exit, "Design graph matches hand-labelled graphs
  on >= 90 % of features". A truth feature is matched by a predicted feature of the
  same type whose parameters all equal the truth within ``value_tol`` (one-to-one,
  greedy). Reported as recall (the plan's measure) and precision.
- **Dimension association**: plan Phase 2 task 2. For each truth dimension, the
  prediction is right when the same DIMENSION handle is linked to the matched
  feature and parameter, or when both truth and prediction say part-level. One
  dimension can locate several aligned features (e.g. two holes at the same x);
  the label names one of them, so any matching link counts.

Uses the parser (block 1) for geometry, so it scores the two blocks together.

Usage: ``uv run python -m edp_eval.suites.interpretation --golden DIR --value-tol T [--out FILE]``
"""

import argparse
import hashlib
import json
from pathlib import Path

from edp_b1_parser import dwg, dxf
from edp_b2_interpretation import interpret
from edp_contracts.artifacts.design_graph import DesignGraph
from edp_eval.synth.labels import LabelFeature, SyntheticLabel

PHASE3_FEATURE_TARGET = 0.90  # plan Phase 3 exit criteria
# Truth dimension targets that belong to a feature; everything else is part-level.
_FEATURE_TARGETS = {"bracket.bend_radius": ("bend", "radius")}


def _truth_owner(target: str, feature_ids: set[str]) -> tuple[str, str] | None:
    if target in _FEATURE_TARGETS:
        return _FEATURE_TARGETS[target]
    fid, _, param = target.partition(".")
    return (fid, param) if fid in feature_ids else None


def _predicted(
    graph: DesignGraph,
) -> tuple[list[tuple[str, str, dict[str, float]]], dict[str, set[tuple[str, str]]]]:
    """(feature id, type, params) and DIMENSION handle -> {(feature id, param)}; empty set = part-level."""
    nodes = {n.id: n for n in graph.nodes}
    features = []
    link: dict[str, set[tuple[str, str]]] = {}
    for f in (n for n in graph.nodes if n.kind == "feature"):
        params: dict[str, float] = {}
        for e in (e for e in graph.edges if e.source == f.id):
            p = nodes[e.target].attributes
            params[p["name"]] = p["value"]
            if p["association"] == "geometric":
                for h in p["dimensions"]:
                    link.setdefault(h, set()).add((f.id, p["name"]))
        features.append((f.id, str(f.feature_type or ""), params))
    for n in graph.nodes:
        if n.kind == "parameter" and n.attributes.get("association") == "part_level":
            for h in n.attributes["dimensions"]:
                link.setdefault(h, set())
    return features, link


def _match(
    truth: list[LabelFeature], pred: list[tuple[str, str, dict[str, float]]], tol: float
) -> dict[str, str]:
    """truth feature id -> predicted feature id."""
    out: dict[str, str] = {}
    used: set[str] = set()
    for t in truth:
        for pid, ptype, params in pred:
            if pid in used or ptype != t.type:
                continue
            if all(k in params and abs(params[k] - v) <= tol for k, v in t.parameters.items()):
                out[t.id] = pid
                used.add(pid)
                break
    return out


def evaluate_drawing(dxf_path: Path, label: SyntheticLabel, value_tol: float) -> dict[str, int]:
    data = dxf_path.read_bytes()
    file_id = hashlib.sha256(data).hexdigest()
    if dxf_path.suffix.lower() == ".dwg":  # converted by LibreDWG first, as in the parser block
        data, _ = dwg.convert(data)
    geometry, _, _ = dxf.parse(data, file_id, "golden")
    graph, flags, _ = interpret(geometry)
    pred, link = _predicted(graph)
    matched = _match(label.features, pred, value_tol)
    ids = {f.id for f in label.features}
    correct = 0
    for d in label.dimensions:
        owner = _truth_owner(d.target, ids)
        got = link.get(d.handle)
        if got is None:  # the dimension is missing from the design graph
            continue
        if owner is None:
            correct += not got
        else:
            correct += (matched.get(owner[0], ""), owner[1]) in got
    return {
        "truth_features": len(label.features),
        "pred_features": len(pred),
        "matched": len(matched),
        "dims": len(label.dimensions),
        "dims_correct": correct,
        "flags": len(flags),
    }


def run(golden: Path, value_tol: float) -> dict:
    totals: dict[str, dict[str, int]] = {}
    for label_path in sorted(golden.glob("*.labels.json")):
        label = SyntheticLabel.model_validate_json(label_path.read_text(encoding="utf-8"))
        if not label.features and label.schema_version < "0.2.0":
            raise ValueError(
                f"{label_path} has label schema {label.schema_version}; regenerate the set (needs 0.2.0)"
            )
        path = golden / f"{label.id}.dxf"
        r = evaluate_drawing(path if path.is_file() else golden / f"{label.id}.dwg", label, value_tol)
        for group in ("overall", f"{label.profile}/{label.family}"):
            acc = totals.setdefault(group, {})
            for k, v in r.items():
                acc[k] = acc.get(k, 0) + v
            acc["drawings"] = acc.get("drawings", 0) + 1

    def scores(c: dict[str, int]) -> dict[str, float | int]:
        return {
            "feature_recall": c["matched"] / c["truth_features"] if c["truth_features"] else 0.0,
            "feature_precision": c["matched"] / c["pred_features"] if c["pred_features"] else 0.0,
            "dimension_association": c["dims_correct"] / c["dims"] if c["dims"] else 0.0,
            "flags": c["flags"],
            "drawings": c["drawings"],
        }

    overall = scores(totals.pop("overall"))
    return {
        "golden": str(golden),
        "settings": {"value_tol": value_tol},
        "overall": overall,
        "phase3_feature_target_met": overall["feature_recall"] >= PHASE3_FEATURE_TARGET,
        "by_group": {g: scores(c) for g, c in sorted(totals.items())},
    }


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m edp_eval.suites.interpretation", description=__doc__)
    ap.add_argument("--golden", type=Path, required=True)
    ap.add_argument("--value-tol", type=float, required=True, help="no default: not set by the plan")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    text = json.dumps(run(args.golden, args.value_tol), indent=2)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()

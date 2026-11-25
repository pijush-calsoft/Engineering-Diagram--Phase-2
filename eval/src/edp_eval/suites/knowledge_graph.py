"""Knowledge Graph evaluation on the family set (plan §7 "Interpretation, KG" row, Phase 3 exit criteria).

Plan Phase 3 exit criteria measured here:

- **Similar-part search top-3 recall >= 0.8 "on a curated set".** The curated set is the
  family set (``edp_eval.synth.write_family_set``): revisions of one part number form one
  group. Per drawing, recall@3 = group members found in the top 3 / min(3, other members).
- **>= 50 % of low-confidence flags correctly resolved by corroboration, and none resolved
  wrongly above 0.9 confidence.** A flag *should* resolve when the drawing's true value
  equals its siblings' dimensioned values; in the adversarial revisions it does not.

The 50 % share depends on the set's mix: by construction half of the omitted values are
adversarial. The checks that do not depend on the mix are reported too: agreeing cases
resolved, disagreeing cases left to a person, wrong resolutions.

Drawings go through blocks 1 and 2 first, so this scores the three blocks together.

Usage: ``uv run python -m edp_eval.suites.knowledge_graph --golden DIR [--out FILE]``
"""

import argparse
import hashlib
import json
from pathlib import Path

from edp_b1_parser import dxf
from edp_b2_interpretation import interpret
from edp_b3_knowledge_graph import SqliteGraphStore, corroborate, ingest, revision_id, similar_parts
from edp_contracts import SourceLocator
from edp_eval.synth.labels import SyntheticLabel

TARGETS = {"recall_at_3": 0.8, "resolved_share": 0.5}  # plan Phase 3 exit criteria
WRONG_CONFIDENCE_LIMIT = 0.9  # "none resolved wrongly above 0.9 confidence"


def run(golden: Path) -> dict:
    labels = [
        SyntheticLabel.model_validate_json(p.read_text(encoding="utf-8"))
        for p in sorted(golden.glob("*.labels.json"))
    ]
    if not labels or any(lb.group is None for lb in labels):
        raise ValueError(f"{golden} is not a family set: every label needs a group (label schema 0.3.0)")
    store = SqliteGraphStore(":memory:")
    parsed = {}
    for lb in labels:
        data = (golden / f"{lb.id}.dxf").read_bytes()
        loc = SourceLocator(file_id=hashlib.sha256(data).hexdigest(), version="golden", confidence=1.0)
        geometry, _, _ = dxf.parse(data, loc.file_id, loc.version)
        graph, _, _ = interpret(geometry)
        rid = ingest(store, graph, geometry.title_block, loc)
        parsed[lb.id] = (graph, rid, revision_id(geometry.title_block, loc)[1])
    by_rid = {parsed[lb.id][1]: lb for lb in labels}

    recalls = []
    counts = {
        "flags": 0,
        "should_resolve": 0,
        "resolved_correct": 0,
        "missed": 0,
        "left_to_person_correctly": 0,
        "resolved_wrongly": 0,
        "resolved_wrongly_above_0_9": 0,
    }
    for lb in labels:
        graph, rid, part_number = parsed[lb.id]
        members = {o.id for o in labels if o.group == lb.group and o.id != lb.id}
        similar = similar_parts(store, graph, exclude=rid, top=3)
        found = {by_rid[s.revision_id].id for s in similar if s.revision_id in by_rid}
        if members:
            recalls.append(len(found & members) / min(3, len(members)))
        if not lb.omitted:
            continue
        truth = {f.id: f.parameters for f in lb.features}["hole1"]["diameter"]
        siblings = [o for o in labels if o.group == lb.group and o.id != lb.id and not o.omitted]
        should = all({f.id: f.parameters for f in o.features}["hole1"]["diameter"] == truth for o in siblings)
        for c in corroborate(store, graph, similar, part_number):
            counts["flags"] += 1
            counts["should_resolve"] += should
            resolved = c.status == "resolved"
            if resolved and should:
                counts["resolved_correct"] += 1
            elif resolved:
                counts["resolved_wrongly"] += 1
                counts["resolved_wrongly_above_0_9"] += c.confidence > WRONG_CONFIDENCE_LIMIT
            elif should:
                counts["missed"] += 1
            else:
                counts["left_to_person_correctly"] += 1
    recall = sum(recalls) / len(recalls) if recalls else 0.0
    flags = counts["flags"]
    resolved_share = counts["resolved_correct"] / flags if flags else 0.0
    return {
        "golden": str(golden),
        "drawings": len(labels),
        "recall_at_3": recall,
        "corroboration": counts | {"resolved_share": resolved_share},
        "targets_met": {
            "recall_at_3": recall >= TARGETS["recall_at_3"],
            "resolved_share": resolved_share >= TARGETS["resolved_share"],
            "none_wrong_above_0_9": counts["resolved_wrongly_above_0_9"] == 0,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m edp_eval.suites.knowledge_graph", description=__doc__)
    ap.add_argument("--golden", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    text = json.dumps(run(args.golden), indent=2)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()

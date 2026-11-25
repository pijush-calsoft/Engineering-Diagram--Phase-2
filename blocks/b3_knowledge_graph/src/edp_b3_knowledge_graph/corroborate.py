"""Corroborate low-confidence values with similar parts (plan Phase 3, KG task 4; principle 3).

"Given a flagged value, look for the same feature in similar parts and return evidence with
its own locators" (plan Phase 3). A value is low-confidence when Interpretation took it from
geometry alone (``association == "geometry_only"``, block 2).

For each such value: in each similar revision, take the feature of the same type closest in
its *other* parameters (for a hole: its position), and use that feature's value only if it
was dimensioned on its drawing.

Which evidence decides: other revisions of the **same part number** when there are any,
because revisions share features unless a change was made on purpose. Other similar parts
are then reported as supporting evidence but do not decide. Without sibling revisions, the
similar parts decide and must agree unanimously. Then, over the deciding evidence:

| outcome | rule | confidence |
|---|---|---|
| ``resolved`` | a dimensioned value agrees, none disagrees | 0.7 + 0.1 per agreeing part, max 0.95 |
| ``conflict`` | at least one dimensioned value disagrees | unchanged; a person decides |
| ``no_evidence`` | no similar part has a dimensioned value for it | unchanged; a person decides |

The value is never replaced: corroboration only confirms it or leaves it to a person.
Confidence values are starting values for calibration (plan Phase 2 task 5).
"""

from typing import Any, Literal

from pydantic import BaseModel

from edp_b3_knowledge_graph.graph import Similar
from edp_b3_knowledge_graph.store import FEATURE, HAS_FEATURE, GraphStore
from edp_contracts import SourceLocator
from edp_contracts.artifacts.design_graph import DesignGraph

AGREE_REL_TOL = 1e-6  # same tolerance idea as block 2's REL_TOL (OD-45)
BASE_CONFIDENCE = 0.7  # block 2's geometry_only confidence
STEP_PER_AGREEMENT = 0.1
MAX_CONFIDENCE = 0.95


class Evidence(BaseModel):
    part_number: str
    revision: str | None
    value: float
    value_mm: float
    agrees: bool
    same_part: bool  # another revision of the same part number: decides when present
    sources: list[SourceLocator]


class Corroboration(BaseModel):
    parameter: str  # design graph node id, e.g. "hole1.diameter"
    feature_type: str
    name: str
    value: float
    value_mm: float | None
    status: Literal["resolved", "conflict", "no_evidence"]
    confidence: float
    evidence: list[Evidence]


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= AGREE_REL_TOL * max(1.0, abs(a), abs(b))


def _distance(a: dict[str, Any], b: dict[str, Any], skip: str) -> float:
    keys = [
        k
        for k in a
        if k != skip and k in b and a[k].get("value_mm") is not None and b[k].get("value_mm") is not None
    ]
    if not keys:
        return 0.0
    return sum(abs(a[k]["value_mm"] - b[k]["value_mm"]) for k in keys) / len(keys)


def corroborate(
    store: GraphStore, graph: DesignGraph, similar: list[Similar], part_number: str
) -> list[Corroboration]:
    nodes = {n.id: n for n in graph.nodes}
    out = []
    for f in (n for n in graph.nodes if n.kind == "feature"):
        mine = {}
        for e in (e for e in graph.edges if e.source == f.id):
            p = nodes[e.target].attributes
            mine[p["name"]] = p
        for name, p in mine.items():
            if p.get("association") != "geometry_only":
                continue
            evidence = []
            for s in similar:
                candidates = [
                    c
                    for c in store.out(s.revision_id, HAS_FEATURE)
                    if c.label == FEATURE
                    and c.props.get("type") == f.feature_type
                    and name in c.props["params"]
                ]
                if not candidates:
                    continue
                best = min(candidates, key=lambda c: _distance(mine, c.props["params"], name))
                theirs = best.props["params"][name]
                if (
                    theirs.get("association") != "geometric"
                    or theirs.get("value_mm") is None
                    or p.get("value_mm") is None
                ):
                    continue
                evidence.append(
                    Evidence(
                        part_number=s.part_number,
                        revision=s.revision,
                        value=theirs["value"],
                        value_mm=theirs["value_mm"],
                        agrees=_close(theirs["value_mm"], p["value_mm"]),
                        same_part=s.part_number == part_number,
                        sources=[SourceLocator.model_validate(x) for x in theirs["sources"]],
                    )
                )
            deciding = [e for e in evidence if e.same_part] or evidence
            agree = sum(e.agrees for e in deciding)
            disagree = len(deciding) - agree
            if agree and not disagree:
                status, conf = "resolved", min(MAX_CONFIDENCE, BASE_CONFIDENCE + STEP_PER_AGREEMENT * agree)
            else:
                status, conf = (
                    ("conflict" if disagree else "no_evidence"),
                    p.get("confidence", BASE_CONFIDENCE),
                )
            out.append(
                Corroboration(
                    parameter=f"{f.id}.{name}",
                    feature_type=f.feature_type or "",
                    name=name,
                    value=p["value"],
                    value_mm=p.get("value_mm"),
                    status=status,
                    confidence=round(conf, 4),
                    evidence=evidence,
                )
            )
    return out

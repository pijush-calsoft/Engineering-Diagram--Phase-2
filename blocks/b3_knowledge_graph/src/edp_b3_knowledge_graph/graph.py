"""Ingest design graphs and find similar parts (plan Phase 3, KG tasks 2 and 3).

**Entities.** Each drawing becomes a Revision of a Part (part number and revision from the
title block), made of a Material, with its Features and the Drawing it came from. Every
feature keeps its parameters and source locators, so evidence can point back to a drawing.

**Similarity.** The plan combines "text embeddings of design graphs with shape descriptors
from trimesh". Neither is available yet: embeddings wait for OD-42, and trimesh descriptors
need 3D input. Until then the descriptor is built from the design graph itself:

- feature counts per type,
- overall (part-level) dimensions in mm, sorted,
- each feature type's parameter values in mm, sorted.

Score = mean of three similarities, each in [0, 1]: counts (1 - L1 / total), overall
dimensions and feature parameters (mean of ``1 - |a - b| / max(a, b)`` over values aligned
by sort order; a missing value scores 0). Equal weights are a starting choice, measured by
the top-3 recall target (plan Phase 3 exit criteria).
"""

from typing import Any

from pydantic import BaseModel

from edp_b3_knowledge_graph.store import (
    DRAWING,
    FEATURE,
    FROM_DRAWING,
    HAS_FEATURE,
    HAS_REVISION,
    MADE_OF,
    MATERIAL,
    PART,
    REVISION,
    Edge,
    GraphStore,
    Node,
)
from edp_contracts import SourceLocator
from edp_contracts.artifacts.design_graph import DesignGraph
from edp_contracts.artifacts.geometry import TitleBlock


class Similar(BaseModel):
    revision_id: str
    part_number: str
    revision: str | None
    score: float
    drawing: SourceLocator | None


def descriptor(graph: DesignGraph) -> dict[str, Any]:
    nodes = {n.id: n for n in graph.nodes}
    counts: dict[str, int] = {}
    params: dict[str, list[float]] = {}
    for f in (n for n in graph.nodes if n.kind == "feature"):
        counts[f.feature_type or ""] = counts.get(f.feature_type or "", 0) + 1
        for e in (e for e in graph.edges if e.source == f.id):
            a = nodes[e.target].attributes
            if a.get("value_mm") is not None:
                params.setdefault(f"{f.feature_type}.{a['name']}", []).append(a["value_mm"])
    dims = sorted(
        n.attributes["value_mm"]
        for n in graph.nodes
        if n.attributes.get("association") == "part_level" and n.attributes.get("value_mm") is not None
    )
    return {"counts": counts, "dims_mm": dims, "params_mm": {k: sorted(v) for k, v in params.items()}}


def _values_sim(a: list[float], b: list[float]) -> float:
    n = max(len(a), len(b))
    if n == 0:
        return 1.0
    total = 0.0
    for x, y in zip(a, b, strict=False):
        top = max(abs(x), abs(y))
        total += 1.0 if top == 0 else max(0.0, 1.0 - abs(x - y) / top)
    return total / n


def similarity(a: dict[str, Any], b: dict[str, Any]) -> float:
    types = set(a["counts"]) | set(b["counts"])
    total = sum(a["counts"].get(t, 0) + b["counts"].get(t, 0) for t in types)
    diff = sum(abs(a["counts"].get(t, 0) - b["counts"].get(t, 0)) for t in types)
    counts = 1.0 if total == 0 else 1.0 - diff / total
    dims = _values_sim(a["dims_mm"], b["dims_mm"])
    keys = set(a["params_mm"]) | set(b["params_mm"])
    params = (
        sum(_values_sim(a["params_mm"].get(k, []), b["params_mm"].get(k, [])) for k in keys) / len(keys)
        if keys
        else 1.0
    )
    return (counts + dims + params) / 3


def revision_id(title: TitleBlock | None, drawing: SourceLocator) -> tuple[str, str, str | None]:
    """(revision node id, part number, revision). Unidentified drawings are keyed by file."""
    pn = title.part_number.value if title and title.part_number and title.part_number.value else None
    rev = title.revision.value if title and title.revision and title.revision.value else None
    part_number = pn or f"unidentified:{drawing.file_id[:16]}"
    return f"rev:{part_number}@{rev or '-'}@{drawing.file_id[:16]}", part_number, rev


def ingest(store: GraphStore, graph: DesignGraph, title: TitleBlock | None, drawing: SourceLocator) -> str:
    """Add or update one drawing's part, revision, material and features. Returns the revision id."""
    rid, part_number, rev = revision_id(title, drawing)
    part_id = f"part:{part_number}"
    store.upsert_node(Node(id=part_id, label=PART, props={"part_number": part_number}))
    store.upsert_node(
        Node(
            id=rid,
            label=REVISION,
            props={"part_number": part_number, "revision": rev, "descriptor": descriptor(graph)},
        )
    )
    store.upsert_edge(Edge(source=part_id, relation=HAS_REVISION, target=rid))
    drawing_id = f"drawing:{drawing.file_id}@{drawing.version}"
    store.upsert_node(Node(id=drawing_id, label=DRAWING, props={"locator": drawing.model_dump(mode="json")}))
    store.upsert_edge(Edge(source=rid, relation=FROM_DRAWING, target=drawing_id))
    if title and title.material and title.material.value:
        mid = f"material:{title.material.value}"
        store.upsert_node(Node(id=mid, label=MATERIAL, props={"name": title.material.value}))
        store.upsert_edge(
            Edge(
                source=rid,
                relation=MADE_OF,
                target=mid,
                props={"source": title.material.locator.model_dump(mode="json")},
            )
        )
    nodes = {n.id: n for n in graph.nodes}
    for f in (n for n in graph.nodes if n.kind == "feature"):
        params = {}
        for e in (e for e in graph.edges if e.source == f.id):
            p = nodes[e.target]
            params[p.attributes["name"]] = {
                "value": p.attributes["value"],
                "unit": p.attributes.get("unit"),
                "value_mm": p.attributes.get("value_mm"),
                "association": p.attributes.get("association"),
                "sources": [s.model_dump(mode="json") for s in p.sources],
            }
        fid = f"{rid}/{f.id}"
        store.upsert_node(Node(id=fid, label=FEATURE, props={"type": f.feature_type, "params": params}))
        store.upsert_edge(Edge(source=rid, relation=HAS_FEATURE, target=fid))
    return rid


def similar_parts(store: GraphStore, graph: DesignGraph, exclude: str | None, top: int) -> list[Similar]:
    """The ``top`` most similar revisions in the store, best first."""
    mine = descriptor(graph)
    scored = []
    for r in store.nodes(REVISION):
        if r.id == exclude:
            continue
        drawings = store.out(r.id, FROM_DRAWING)
        loc = SourceLocator.model_validate(drawings[0].props["locator"]) if drawings else None
        scored.append(
            Similar(
                revision_id=r.id,
                part_number=r.props["part_number"],
                revision=r.props.get("revision"),
                score=round(similarity(mine, r.props["descriptor"]), 6),
                drawing=loc,
            )
        )
    scored.sort(key=lambda s: (-s.score, s.revision_id))
    return scored[:top]

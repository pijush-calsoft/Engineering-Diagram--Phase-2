"""Block 3, Knowledge Graph, as a plug-in (plan §3, Phase 3).

Takes the run's geometry (for the title block) and design graph. Looks up similar parts
already in the graph, corroborates low-confidence values, then adds this drawing to the
graph. Output: a ``similar_parts`` artifact with the similar revisions and every
corroboration with its evidence. Values it cannot settle are flagged for a person
(plan principle 3), which pauses the run.
"""

import json
import os
from pathlib import Path

from edp_b3_knowledge_graph.corroborate import corroborate
from edp_b3_knowledge_graph.graph import ingest, revision_id, similar_parts
from edp_b3_knowledge_graph.store import GraphStore, SqliteGraphStore
from edp_contracts import Artifact, BlockRequest, BlockResult, Flag, SourceLocator
from edp_contracts.artifacts.design_graph import DesignGraph
from edp_contracts.artifacts.geometry import Geometry
from edp_kit import ArtifactStore

SCHEMA_VERSION = "0.1.0"
TOP_SIMILAR = 3  # plan Phase 3 exit: "similar-part search top-3 recall"


class KnowledgeGraph:
    name = "b3_knowledge_graph"
    version = "0.1.0"
    accepts = {"geometry", "design_graph"}
    produces = {"similar_parts"}

    def __init__(self, store: ArtifactStore | None = None, graph: GraphStore | None = None) -> None:
        self._store = store
        self._graph = graph

    def _data_dir(self) -> Path:
        data_dir = os.environ.get("EDP_DATA_DIR")
        if not data_dir:
            raise RuntimeError("KnowledgeGraph needs stores, or EDP_DATA_DIR set to the local data folder")
        return Path(data_dir)

    @property
    def store(self) -> ArtifactStore:
        if self._store is None:
            from edp_fabric import FabricStore  # entry-point loading: local Fabric (ADR-0008)

            self._store = FabricStore(self._data_dir() / "fabric")
        return self._store

    @property
    def graph(self) -> GraphStore:
        if self._graph is None:
            self._graph = SqliteGraphStore(self._data_dir() / "knowledge_graph.sqlite")
        return self._graph

    def run(self, req: BlockRequest) -> BlockResult:
        geometries = {a.sources[0].file_id: a for a in req.inputs if a.kind == "geometry" and a.sources}
        outputs: list[Artifact] = []
        flags: list[Flag] = []
        metrics: dict[str, object] = {}
        for i, art in enumerate(a for a in req.inputs if a.kind == "design_graph"):
            drawing = art.sources[0] if art.sources else None
            geo_art = geometries.get(drawing.file_id) if drawing else None
            if drawing is None or geo_art is None:
                raise ValueError(f"design graph {art.uri} has no matching geometry input")
            graph = DesignGraph.model_validate_json(self.store.read(art.uri))
            title = Geometry.model_validate_json(self.store.read(geo_art.uri)).title_block
            rid, part_number, revision = revision_id(title, drawing)
            similar = similar_parts(self.graph, graph, exclude=rid, top=TOP_SIMILAR)
            corroborations = corroborate(self.graph, graph, similar, part_number)
            ingest(self.graph, graph, title, drawing)
            for c in corroborations:
                flags.append(self._flag(c.status, c.parameter, c.value, len(c.evidence), drawing))
            body = {
                "part": {"revision_id": rid, "part_number": part_number, "revision": revision},
                "similar": [s.model_dump(mode="json") for s in similar],
                "corroborations": [c.model_dump(mode="json") for c in corroborations],
            }
            uri = self.store.write(
                req.run_id, self.name, f"similar_parts-{i}.json", json.dumps(body).encode()
            )
            outputs.append(
                Artifact(kind="similar_parts", uri=uri, schema_version=SCHEMA_VERSION, sources=[drawing])
            )
            metrics[art.uri] = {
                "similar": len(similar),
                "corroborations": {
                    s: sum(c.status == s for c in corroborations)
                    for s in ("resolved", "conflict", "no_evidence")
                },
            }
        review = any(f.severity in ("review", "block") for f in flags)
        return BlockResult(
            run_id=req.run_id,
            status="needs_review" if review else "ok",
            outputs=outputs,
            flags=flags,
            metrics=metrics,
        )

    @staticmethod
    def _flag(status: str, parameter: str, value: float, n: int, drawing: SourceLocator) -> Flag:
        if status == "resolved":
            return Flag(
                code="CORROBORATED",
                severity="info",
                target=drawing,
                message=f"{parameter} = {value:g} confirmed by {n} similar part(s)",
            )
        reason = "CONFLICTING_EVIDENCE" if status == "conflict" else "NO_EVIDENCE"
        return Flag(
            code="LOW_CONFIDENCE",
            severity="review",
            target=drawing,
            message=f"[{reason}] {parameter} = {value:g} taken from geometry; similar parts "
            f"{'disagree' if status == 'conflict' else 'give no dimensioned value'}",
        )

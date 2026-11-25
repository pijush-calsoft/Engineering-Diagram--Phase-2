"""Block 2, Interpretation, as a plug-in (plan §3, Phase 3): geometry in, design graph out."""

import os
from pathlib import Path

from edp_b2_interpretation.graph import interpret
from edp_contracts import Artifact, BlockRequest, BlockResult, Flag
from edp_contracts.artifacts.design_graph import SCHEMA_VERSION
from edp_contracts.artifacts.geometry import Geometry
from edp_kit import ArtifactStore


class Interpretation:
    name = "b2_interpretation"
    version = "0.1.0"
    accepts = {"geometry"}
    produces = {"design_graph"}

    def __init__(self, store: ArtifactStore | None = None) -> None:
        self._store = store

    @property
    def store(self) -> ArtifactStore:
        if self._store is None:
            from edp_fabric import FabricStore  # entry-point loading: local Fabric (ADR-0008)

            data_dir = os.environ.get("EDP_DATA_DIR")
            if not data_dir:
                raise RuntimeError(
                    "Interpretation needs a store, or EDP_DATA_DIR set to the local data folder"
                )
            self._store = FabricStore(Path(data_dir) / "fabric")
        return self._store

    def run(self, req: BlockRequest) -> BlockResult:
        outputs: list[Artifact] = []
        flags: list[Flag] = []
        metrics: dict[str, object] = {}
        for i, art in enumerate(req.inputs):
            geometry = Geometry.model_validate_json(self.store.read(art.uri))
            graph, graph_flags, m = interpret(geometry)
            uri = self.store.write(
                req.run_id, self.name, f"design_graph-{i}.json", graph.model_dump_json().encode()
            )
            outputs.append(
                Artifact(kind="design_graph", uri=uri, schema_version=SCHEMA_VERSION, sources=art.sources)
            )
            flags.extend(graph_flags)
            metrics[art.uri] = m
        # Plan principle 3: low-confidence flags go to the Knowledge Graph for corroboration
        # first (block 3), and to a person only if still unresolved. Other review flags
        # (contradictions, features outside the part, unknown units) stop here.
        review = any(f.severity in ("review", "block") and f.code != "LOW_CONFIDENCE" for f in flags)
        return BlockResult(
            run_id=req.run_id,
            status="needs_review" if review else "ok",
            outputs=outputs,
            flags=flags,
            metrics=metrics,
        )

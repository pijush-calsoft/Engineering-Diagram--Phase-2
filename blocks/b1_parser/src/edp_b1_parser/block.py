"""Block 1, Drawing Parser, as a plug-in (plan §3, Phase 2).

Accepts DXF for now. DWG (LibreDWG ``dwg2dxf``), vector PDF, scans (ADR-0007),
STEP/IGES and STL follow in Phase 2. Writes the ``geometry`` artifact to the
Data Fabric's cleaned zone (deck slide 30).
"""

import os
import time
from pathlib import Path

from edp_b1_parser import dxf
from edp_contracts import Artifact, BlockRequest, BlockResult, Flag
from edp_contracts.artifacts.geometry import SCHEMA_VERSION
from edp_kit import ArtifactStore


class DrawingParser:
    name = "b1_parser"
    version = "0.1.0"
    accepts = {"dxf"}
    produces = {"geometry"}

    def __init__(self, store: ArtifactStore | None = None) -> None:
        self._store = store

    @property
    def store(self) -> ArtifactStore:
        if self._store is None:
            # Entry-point loading builds the block without arguments; use the local Fabric (ADR-0008).
            from edp_fabric import FabricStore

            data_dir = os.environ.get("EDP_DATA_DIR")
            if not data_dir:
                raise RuntimeError(
                    "DrawingParser needs a store, or EDP_DATA_DIR set to the local data folder"
                )
            self._store = FabricStore(Path(data_dir) / "fabric")
        return self._store

    def run(self, req: BlockRequest) -> BlockResult:
        outputs: list[Artifact] = []
        flags: list[Flag] = []
        metrics: dict[str, object] = {}
        for i, art in enumerate(req.inputs):
            if not art.sources:
                raise ValueError(f"input {art.uri} has no source locator for the file version")
            src = art.sources[0]
            started = time.perf_counter()
            geometry, file_flags, file_metrics = dxf.parse(self.store.read(art.uri), src.file_id, src.version)
            uri = self.store.write(
                req.run_id, self.name, f"geometry-{i}.json", geometry.model_dump_json().encode("utf-8")
            )
            outputs.append(Artifact(kind="geometry", uri=uri, schema_version=SCHEMA_VERSION, sources=[src]))
            flags.extend(file_flags)
            metrics[art.uri] = file_metrics | {"seconds": round(time.perf_counter() - started, 4)}
        review = any(f.severity in ("review", "block") for f in flags)
        return BlockResult(
            run_id=req.run_id,
            status="needs_review" if review else "ok",
            outputs=outputs,
            flags=flags,
            metrics=metrics,
        )

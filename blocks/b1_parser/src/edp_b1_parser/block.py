"""Block 1, Drawing Parser, as a plug-in (plan §3, Phase 2).

Accepts DXF, DWG through LibreDWG ``dwg2dxf`` (``edp_b1_parser.dwg``), vector PDF
(``edp_b1_parser.pdf``), and STEP, IGES and STL (``edp_b1_parser.model3d``). Scans go
through the multimodal path (ADR-0007), not built yet (OD-43). Writes the ``geometry`` artifact to the
Data Fabric's cleaned zone (deck slide 30).
"""

import os
import time
from pathlib import Path

from edp_b1_parser import dwg, dxf, model3d, pdf
from edp_contracts import Artifact, BlockRequest, BlockResult, Flag
from edp_contracts.artifacts.geometry import SCHEMA_VERSION
from edp_kit import ArtifactStore


class DrawingParser:
    name = "b1_parser"
    version = "0.1.0"
    accepts = {"dxf", "dwg", "pdf", "step", "iges", "stl"}
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
            data = self.store.read(art.uri)
            conversion: list[Flag] = []
            if art.kind == "dwg":
                try:
                    data, conversion = dwg.convert(data)
                except dwg.DwgConversionError as exc:
                    flags.append(
                        Flag(code="DWG_CONVERSION_FAILED", severity="block", target=src, message=str(exc))
                    )
                    continue
            # Locators keep the uploaded file's id and version: for a DWG they point at the DWG.
            if art.kind in ("step", "iges"):
                geometry, file_flags, file_metrics = model3d.parse_brep(
                    data, art.kind, src.file_id, src.version
                )
            elif art.kind == "stl":
                geometry, file_flags, file_metrics = model3d.parse_stl(data, src.file_id, src.version)
            else:
                reader = pdf.parse if art.kind == "pdf" else dxf.parse
                geometry, file_flags, file_metrics = reader(data, src.file_id, src.version)
            file_flags = conversion + file_flags
            uri = self.store.write(
                req.run_id, self.name, f"geometry-{i}.json", geometry.model_dump_json().encode("utf-8")
            )
            outputs.append(Artifact(kind="geometry", uri=uri, schema_version=SCHEMA_VERSION, sources=[src]))
            flags.extend(file_flags)
            metrics[art.uri] = file_metrics | {"seconds": round(time.perf_counter() - started, 4)}
        if any(f.severity == "block" for f in flags) and not outputs:
            return BlockResult(run_id=req.run_id, status="failed", outputs=[], flags=flags, metrics=metrics)
        review = any(f.severity in ("review", "block") for f in flags)
        return BlockResult(
            run_id=req.run_id,
            status="needs_review" if review else "ok",
            outputs=outputs,
            flags=flags,
            metrics=metrics,
        )

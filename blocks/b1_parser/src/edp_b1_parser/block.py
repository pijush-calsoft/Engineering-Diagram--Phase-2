"""Block 1, Drawing Parser, as a plug-in (plan §3, Phase 2).

Accepts DXF, DWG through LibreDWG ``dwg2dxf`` (``edp_b1_parser.dwg``), vector PDF
(``edp_b1_parser.pdf``), STEP, IGES and STL (``edp_b1_parser.model3d``), and scans: images and
PDFs whose pages hold only images (``edp_b1_parser.scan``, ADR-0007), read by the multimodal
model through the Model Gateway. Writes the ``geometry`` artifact to the Data Fabric's cleaned
zone (deck slide 30).

Scans are sent only when the run's ``data_class`` (request parameter, OD-39) allows images: a
client scan is refused by the gateway until title-block masking exists (OD-51).
"""

import os
import time
from pathlib import Path

from edp_b1_parser import dwg, dxf, model3d, pdf, scan
from edp_b1_parser.annotations import annotation_flags
from edp_contracts import Artifact, BlockRequest, BlockResult, Flag
from edp_contracts.artifacts.geometry import SCHEMA_VERSION
from edp_gateway import Gateway, GatewayConfig, ImageNotAllowed
from edp_kit import ArtifactStore


class DrawingParser:
    name = "b1_parser"
    version = "0.1.0"
    accepts = {"dxf", "dwg", "pdf", "step", "iges", "stl", "image"}
    produces = {"geometry"}

    def __init__(self, store: ArtifactStore | None = None, gateway: Gateway | None = None) -> None:
        self._store = store
        self._gateway = gateway

    @property
    def gateway(self) -> Gateway:
        if self._gateway is None:
            self._gateway = Gateway(GatewayConfig.load())
        return self._gateway

    def _scan(self, data: bytes, kind: str, src, req: BlockRequest):  # noqa: ANN001, ANN202
        """Read a scan; on refusal or failure, a blocking flag instead of a geometry."""
        data_class = req.params.get("data_class", "client")  # unknown origin: treat as client data
        try:
            return scan.parse(data, kind, src.file_id, src.version, self.gateway, data_class, req.run_id)  # type: ignore[arg-type]
        except ImageNotAllowed as exc:
            message = f"scan not sent to the model: {exc}"
        except Exception as exc:  # noqa: BLE001 - provider and decoding errors: report the type
            message = f"scan could not be read ({type(exc).__name__}: {str(exc)[:200]})"
        return None, [Flag(code="SCAN_NOT_READ", severity="block", target=src, message=message)], {}

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
            elif art.kind == "image":
                geometry, file_flags, file_metrics = self._scan(data, "image", src, req)
            else:
                reader = pdf.parse if art.kind == "pdf" else dxf.parse
                geometry, file_flags, file_metrics = reader(data, src.file_id, src.version)
                scanned = any(f.code == "SCANNED_PDF" for f in file_flags)
                if art.kind == "pdf" and not geometry.entities and scanned:
                    geometry, file_flags, file_metrics = self._scan(data, "pdf", src, req)
            if geometry is None:
                flags.extend(file_flags)
                continue
            file_flags = conversion + file_flags
            file_flags += annotation_flags(geometry, art.kind, file_metrics.get("skipped"))
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

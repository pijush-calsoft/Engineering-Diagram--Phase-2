"""Data Fabric HTTP API: upload and promotion (plan Phase 1)."""

from fastapi import FastAPI, HTTPException, UploadFile

from edp_fabric.filetype import UnsupportedTypeError
from edp_fabric.store import Commit, FabricStore, IngestResult, Zone


def create_app(store: FabricStore) -> FastAPI:
    app = FastAPI(title="EDP Data Fabric")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/files", response_model=IngestResult)
    async def upload(file: UploadFile, uploader: str) -> IngestResult:
        data = await file.read()
        try:
            return store.ingest(file.filename or "upload", data, uploader)
        except UnsupportedTypeError as exc:
            raise HTTPException(status_code=415, detail={"code": exc.code, "message": str(exc)}) from exc

    @app.post("/datasets/{dataset_id}/promote", response_model=Commit)
    def promote(dataset_id: str, from_zone: Zone, to_zone: Zone) -> Commit:
        try:
            return store.promote(dataset_id, from_zone, to_zone)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return app

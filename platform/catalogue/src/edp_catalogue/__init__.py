"""Data Catalogue: artifact registry and element-level lineage (plan Phase 1; ADR-0008)."""

from fastapi import FastAPI, HTTPException

from edp_catalogue.catalogue import ArtifactRecord, Catalogue
from edp_contracts import SourceLocator


def create_app(catalogue: Catalogue) -> FastAPI:
    app = FastAPI(title="EDP Data Catalogue")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/runs/{run_id}/artifacts", response_model=list[ArtifactRecord])
    def run_artifacts(run_id: str) -> list[ArtifactRecord]:
        return catalogue.by_run(run_id)

    @app.get("/artifacts/{artifact_id}/lineage", response_model=list[SourceLocator])
    def lineage(artifact_id: str) -> list[SourceLocator]:
        try:
            catalogue.get(artifact_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"unknown artifact {artifact_id}") from exc
        return catalogue.lineage(artifact_id)

    @app.get("/files/{file_id}/derived", response_model=list[ArtifactRecord])
    def derived(file_id: str) -> list[ArtifactRecord]:
        return catalogue.derived_from(file_id)

    return app


__all__ = ["ArtifactRecord", "Catalogue", "create_app"]

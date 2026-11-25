"""Data Catalogue, SQLite adapter (plan Phase 1; ADR-0008).

Artifact registry and element-level lineage table (plan Phase 1). Every
registered artifact keeps its source locators, so any output can be traced
back to the drawing, file version or run that produced it (plan principle 1).
Publishes ``catalogue.lineage.recorded`` with output item and source locators
(Appendix B). PostgreSQL replaces SQLite, and dataset-level lineage goes to
Marquez through OpenLineage, when those services run.

Not built yet: the vector index and the "cited answer" endpoint, which need an
embedding model (OD-42).
"""

import json
import sqlite3
import uuid
from pathlib import Path

from pydantic import BaseModel

from edp_contracts import Artifact, SourceLocator
from edp_contracts.events import CATALOGUE_LINEAGE_RECORDED
from edp_kit.events import EventBus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS artifact (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    block TEXT NOT NULL,
    block_version TEXT NOT NULL,
    kind TEXT NOT NULL,
    uri TEXT NOT NULL,
    schema_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lineage (
    artifact_id TEXT NOT NULL REFERENCES artifact(id),
    position INTEGER NOT NULL,
    file_id TEXT NOT NULL,
    version TEXT NOT NULL,
    locator TEXT NOT NULL,
    PRIMARY KEY (artifact_id, position)
);
CREATE INDEX IF NOT EXISTS lineage_file ON lineage(file_id);
CREATE INDEX IF NOT EXISTS artifact_run ON artifact(run_id);
"""


class ArtifactRecord(BaseModel):
    id: str
    run_id: str
    block: str
    block_version: str
    artifact: Artifact


class Catalogue:
    def __init__(self, path: Path | str, bus: EventBus | None = None) -> None:
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.executescript(_SCHEMA)
        self.bus = bus

    def register(self, run_id: str, block: str, block_version: str, artifact: Artifact) -> str:
        artifact_id = f"art-{uuid.uuid4().hex[:16]}"
        with self.db:
            self.db.execute(
                "INSERT INTO artifact VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    artifact_id,
                    run_id,
                    block,
                    block_version,
                    artifact.kind,
                    artifact.uri,
                    artifact.schema_version,
                ),
            )
            self.db.executemany(
                "INSERT INTO lineage VALUES (?, ?, ?, ?, ?)",
                [
                    (artifact_id, i, s.file_id, s.version, s.model_dump_json())
                    for i, s in enumerate(artifact.sources)
                ],
            )
        if self.bus:
            self.bus.publish(
                CATALOGUE_LINEAGE_RECORDED,
                {
                    "output_item": artifact_id,
                    "source_locators": [json.loads(s.model_dump_json()) for s in artifact.sources],
                },
            )
        return artifact_id

    def get(self, artifact_id: str) -> ArtifactRecord:
        row = self.db.execute("SELECT * FROM artifact WHERE id = ?", (artifact_id,)).fetchone()
        if row is None:
            raise KeyError(artifact_id)
        return self._record(row)

    def lineage(self, artifact_id: str) -> list[SourceLocator]:
        rows = self.db.execute(
            "SELECT locator FROM lineage WHERE artifact_id = ? ORDER BY position", (artifact_id,)
        ).fetchall()
        return [SourceLocator.model_validate_json(r[0]) for r in rows]

    def by_run(self, run_id: str) -> list[ArtifactRecord]:
        rows = self.db.execute("SELECT * FROM artifact WHERE run_id = ? ORDER BY rowid", (run_id,)).fetchall()
        return [self._record(r) for r in rows]

    def derived_from(self, file_id: str) -> list[ArtifactRecord]:
        """Every artifact with a source locator pointing at ``file_id``."""
        rows = self.db.execute(
            "SELECT DISTINCT a.* FROM artifact a JOIN lineage l ON l.artifact_id = a.id "
            "WHERE l.file_id = ? ORDER BY a.rowid",
            (file_id,),
        ).fetchall()
        return [self._record(r) for r in rows]

    def _record(self, row: tuple) -> ArtifactRecord:
        artifact_id, run_id, block, block_version, kind, uri, schema_version = row
        artifact = Artifact(
            kind=kind, uri=uri, schema_version=schema_version, sources=self.lineage(artifact_id)
        )
        return ArtifactRecord(
            id=artifact_id, run_id=run_id, block=block, block_version=block_version, artifact=artifact
        )

"""Data Fabric, local filesystem adapter (plan Phase 1; ADR-0008).

Zones raw, cleaned and final (plan Phase 1: "raw/cleaned/final zones as lakeFS
branches"). Each dataset version is an immutable commit whose id becomes
``SourceLocator.version`` (plan §4.1 lakeFS row). Raw files never change; a
correction creates a new version (deck slide 39). lakeFS and SeaweedFS replace
this adapter later.

Layout: ``<root>/<zone>/<dataset_id>/<commit>/<filename>`` plus ``commit.json``.
URIs: ``fabric://<zone>/<dataset_id>/<commit>/<filename>``.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from edp_contracts import Artifact, SourceLocator
from edp_contracts.events import FABRIC_DATASET_PROMOTED, FABRIC_DATASET_VERSIONED, FABRIC_FILE_INGESTED
from edp_fabric.filetype import FileKind, detect
from edp_kit.events import EventBus

Zone = Literal["raw", "cleaned", "final"]
ZONES: tuple[Zone, ...] = ("raw", "cleaned", "final")
SCHEME = "fabric://"
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]")


class Commit(BaseModel):
    commit: str
    zone: Zone
    dataset_id: str
    files: dict[str, str]  # filename -> sha256
    parent: str | None = None
    message: str


class IngestResult(BaseModel):
    file_id: str  # sha256 of the content
    dataset_id: str
    commit: str
    kind: FileKind
    filename: str
    uri: str
    warning: str | None = None

    def as_artifact(self) -> Artifact:
        """The uploaded file as a pipeline input, with a whole-file source locator."""
        loc = SourceLocator(file_id=self.file_id, version=self.commit, confidence=1.0)
        return Artifact(kind=self.kind, uri=self.uri, schema_version="file", sources=[loc])


class FabricStore:
    def __init__(self, root: Path, bus: EventBus | None = None) -> None:
        self.root = root
        self.bus = bus

    def ingest(self, filename: str, data: bytes, uploader: str) -> IngestResult:
        """Store a new file in the raw zone as a new dataset with one commit."""
        detection = detect(data, filename)  # raises UnsupportedTypeError
        sha = hashlib.sha256(data).hexdigest()
        name = _SAFE_NAME.sub("_", Path(filename).name) or "file"
        dataset_id = f"ds-{sha[:16]}"
        commit = self._write_commit("raw", dataset_id, {name: data}, parent=None, message=f"ingest {name}")
        result = IngestResult(
            file_id=sha,
            dataset_id=dataset_id,
            commit=commit.commit,
            kind=detection.kind,
            filename=name,
            uri=self.uri("raw", dataset_id, commit.commit, name),
            warning=detection.warning,
        )
        self._publish(
            FABRIC_FILE_INGESTED, {"file_id": sha, "type": detection.kind, "hash": sha, "uploader": uploader}
        )
        self._publish(FABRIC_DATASET_VERSIONED, {"dataset_id": dataset_id, "commit": commit.commit})
        return result

    def promote(self, dataset_id: str, from_zone: Zone, to_zone: Zone) -> Commit:
        """Copy the latest commit of a dataset to the next zone (raw -> cleaned -> final)."""
        if ZONES.index(to_zone) != ZONES.index(from_zone) + 1:
            raise ValueError(f"promotion must go one zone forward, not {from_zone} -> {to_zone}")
        src = self.latest(from_zone, dataset_id)
        data = {n: (self._commit_dir(from_zone, dataset_id, src.commit) / n).read_bytes() for n in src.files}
        commit = self._write_commit(
            to_zone, dataset_id, data, parent=src.commit, message=f"promote {from_zone} -> {to_zone}"
        )
        self._publish(
            FABRIC_DATASET_PROMOTED, {"dataset_id": dataset_id, "from_zone": from_zone, "to_zone": to_zone}
        )
        self._publish(FABRIC_DATASET_VERSIONED, {"dataset_id": dataset_id, "commit": commit.commit})
        return commit

    def latest(self, zone: Zone, dataset_id: str) -> Commit:
        commits = [
            Commit.model_validate_json(p.read_text(encoding="utf-8"))
            for p in (self.root / zone / dataset_id).glob("*/commit.json")
        ]
        if not commits:
            raise KeyError(f"no commit for {dataset_id} in {zone}")
        children = {c.parent for c in commits}
        heads = [c for c in commits if c.commit not in children]
        return heads[0]

    def read(self, uri: str) -> bytes:
        return self.resolve(uri).read_bytes()

    def write(self, run_id: str, block: str, name: str, data: bytes) -> str:
        """Store a block output in the cleaned zone and return its URI.

        Deck slide 30: "The Drawing Parser works here, from raw to cleaned". Each
        write is a new commit on the run's dataset; earlier outputs stay readable.
        """
        dataset_id = f"run-{_SAFE_NAME.sub('_', run_id)}"
        filename = _SAFE_NAME.sub("_", f"{block}.{name}")
        try:
            parent: Commit | None = self.latest("cleaned", dataset_id)
        except KeyError:
            parent = None
        files = (
            {}
            if parent is None
            else {
                n: (self._commit_dir("cleaned", dataset_id, parent.commit) / n).read_bytes()
                for n in parent.files
            }
        )
        files[filename] = data
        commit = self._write_commit(
            "cleaned",
            dataset_id,
            files,
            parent=parent.commit if parent else None,
            message=f"{block} output {filename}",
        )
        self._publish(FABRIC_DATASET_VERSIONED, {"dataset_id": dataset_id, "commit": commit.commit})
        return self.uri("cleaned", dataset_id, commit.commit, filename)

    def resolve(self, uri: str) -> Path:
        if not uri.startswith(SCHEME):
            raise ValueError(f"not a fabric URI: {uri}")
        zone, dataset_id, commit, name = uri[len(SCHEME) :].split("/", 3)
        if zone not in ZONES:
            raise ValueError(f"unknown zone in {uri}")
        path = self._commit_dir(zone, dataset_id, commit) / name  # type: ignore[arg-type]
        if not path.resolve().is_relative_to(self.root.resolve()):
            raise ValueError(f"URI escapes the fabric root: {uri}")
        return path

    @staticmethod
    def uri(zone: Zone, dataset_id: str, commit: str, name: str) -> str:
        return f"{SCHEME}{zone}/{dataset_id}/{commit}/{name}"

    def _commit_dir(self, zone: Zone, dataset_id: str, commit: str) -> Path:
        return self.root / zone / dataset_id / commit

    def _write_commit(
        self, zone: Zone, dataset_id: str, files: dict[str, bytes], parent: str | None, message: str
    ) -> Commit:
        hashes = {n: hashlib.sha256(b).hexdigest() for n, b in sorted(files.items())}
        key = json.dumps(
            {"zone": zone, "dataset": dataset_id, "files": hashes, "parent": parent}, sort_keys=True
        )
        commit = Commit(
            commit=hashlib.sha256(key.encode()).hexdigest()[:20],
            zone=zone,
            dataset_id=dataset_id,
            files=hashes,
            parent=parent,
            message=message,
        )
        target = self._commit_dir(zone, dataset_id, commit.commit)
        target.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            path = target / name
            if not path.exists():  # commits are immutable
                path.write_bytes(data)
        (target / "commit.json").write_text(commit.model_dump_json(indent=2), encoding="utf-8")
        return commit

    def _publish(self, subject: str, payload: dict) -> None:
        if self.bus:
            self.bus.publish(subject, payload)

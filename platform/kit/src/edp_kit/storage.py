"""Artifact storage interface for blocks (plan §3: ``Artifact.uri`` points inside the Data Fabric).

``edp_fabric.FabricStore`` implements it locally (ADR-0008).
"""

from typing import Protocol


class ArtifactStore(Protocol):
    def read(self, uri: str) -> bytes: ...
    def write(self, run_id: str, block: str, name: str, data: bytes) -> str: ...

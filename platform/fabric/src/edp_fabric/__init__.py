"""Data Fabric: upload, type check, zones and versions (plan Phase 1; ADR-0008)."""

from edp_fabric.filetype import Detection, UnsupportedTypeError, detect
from edp_fabric.store import ZONES, Commit, FabricStore, IngestResult

__all__ = ["ZONES", "Commit", "Detection", "FabricStore", "IngestResult", "UnsupportedTypeError", "detect"]

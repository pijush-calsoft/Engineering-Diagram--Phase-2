"""Artifact schemas v0.1 named in plan Phase 0, task 4."""

from pydantic import BaseModel

from edp_contracts.artifacts.cad_script import CadScript
from edp_contracts.artifacts.design_graph import DesignGraph
from edp_contracts.artifacts.geometry import Geometry
from edp_contracts.artifacts.margins import Margins
from edp_contracts.artifacts.report import Report

# Artifact.kind -> payload model. "step" and other binary kinds have no JSON payload.
ARTIFACT_MODELS: dict[str, type[BaseModel]] = {
    "geometry": Geometry,
    "design_graph": DesignGraph,
    "cad_script": CadScript,
    "margins": Margins,
    "report": Report,
}

__all__ = ["ARTIFACT_MODELS", "CadScript", "DesignGraph", "Geometry", "Margins", "Report"]

"""``design_graph`` artifact, schema v0.1.

Source: plan Phase 3, Interpretation task 1. The design graph holds features
(hole, slot, pocket, boss, fillet, rib, bend), parameters, tolerances, datums,
materials, requirements, and edges between them.

Nodes carry source locators (guiding principle 1). Edge relation names are
left as free text until the Phase 3 schema work fixes them.
"""

from typing import Literal

from pydantic import BaseModel, model_validator

from edp_contracts.block import SourceLocator

SCHEMA_VERSION = "0.1.0"

NodeKind = Literal["feature", "parameter", "tolerance", "datum", "material", "requirement"]
FeatureType = Literal["hole", "slot", "pocket", "boss", "fillet", "rib", "bend"]


class DesignNode(BaseModel):
    id: str
    kind: NodeKind
    feature_type: FeatureType | None = None   # set only when kind == "feature"
    attributes: dict = {}
    sources: list[SourceLocator] = []

    @model_validator(mode="after")
    def _feature_type_only_on_features(self) -> "DesignNode":
        if (self.kind == "feature") != (self.feature_type is not None):
            raise ValueError("feature_type is required for features and forbidden otherwise")
        return self


class DesignEdge(BaseModel):
    source: str
    target: str
    relation: str


class DesignGraph(BaseModel):
    schema_version: str = SCHEMA_VERSION
    nodes: list[DesignNode] = []
    edges: list[DesignEdge] = []

    @model_validator(mode="after")
    def _edges_reference_nodes(self) -> "DesignGraph":
        ids = [n.id for n in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("node ids must be unique")
        known = set(ids)
        for e in self.edges:
            if e.source not in known or e.target not in known:
                raise ValueError(f"edge {e.source}->{e.target} references an unknown node")
        return self

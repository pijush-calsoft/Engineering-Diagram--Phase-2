"""Ground-truth label format for synthetic drawings.

Labels are exact by construction: every value is the parameter the geometry was
drawn from. The label export format for hand-labelled data is still open (see
eval/README.md); this format covers synthetic data only.
"""

from typing import Literal

from pydantic import BaseModel

LABEL_SCHEMA_VERSION = "0.1.0"

DimensionKind = Literal["linear", "diameter", "radius"]


class LabelDimension(BaseModel):
    target: str  # feature id the dimension measures, e.g. "hole1.diameter"
    value: float  # in the drawing's units
    kind: DimensionKind
    view: str
    handle: str  # DXF handle of the DIMENSION entity (source locator)


class LabelText(BaseModel):
    value: str
    handle: str  # DXF handle of the TEXT entity


class SyntheticLabel(BaseModel):
    schema_version: str = LABEL_SCHEMA_VERSION
    id: str
    family: str
    profile: str
    projection: str
    units: str
    seed: int
    views: list[str]
    parameters: dict[str, float]
    dimensions: list[LabelDimension]
    title_block: dict[str, LabelText]

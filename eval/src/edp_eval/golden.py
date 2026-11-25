"""Golden-dataset manifest, v0.1.

Source: plan Phase 0, key task 2 and exit criteria; guiding principle 7;
Appendix A (``eval/golden/`` holds dataset manifests, data lives in the fabric).

Plan Phase 0 task 2: "60 to 100 drawings across DXF, DWG, vector PDF and
scans, plus 20 STEP/STL models, with hand-labelled ground truth (geometry,
dimensions, tolerances, title block fields, material, expected parameters).
Use only internal or openly licensed drawings; client drawings are used only
inside that client's scope."

Plan Phase 0 exit criterion: "golden dataset has at least 60 labelled drawings".

The manifest only points at data. Drawings, models and labels live in the
Data Fabric (Appendix A: "data lives in the fabric"). Keeping them out of
git is a repo rule (root .gitignore). Client data also stays in client
scope (principle 7). Part families are not decided yet
(OD-1, OD-12), and the data source is not decided yet (OD-7, OD-17), so
``part_family`` is a free string and no item list is shipped.
"""

from collections import Counter
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints, field_validator, model_validator

MANIFEST_SCHEMA_VERSION = "0.1.0"

# R1 input types (plan section 2.1 inputs, Phase 2 "Approach by input").
InputFormat = Literal["dxf", "dwg", "pdf_vector", "scan", "step", "iges", "stl"]

# "Drawings" in Phase 0 task 2 and the exit criterion: DXF, DWG, vector PDF and scans.
DRAWING_FORMATS: frozenset[str] = frozenset({"dxf", "dwg", "pdf_vector", "scan"})

# Phase 0 task 2 counts "20 STEP/STL models". IGES is also a 3D input (plan 2.1),
# but the plan's count names STEP and STL only, so only those two are counted here.
COUNTED_MODEL_FORMATS: frozenset[str] = frozenset({"step", "stl"})

# Ground-truth categories listed in Phase 0 task 2.
LabelField = Literal["geometry", "dimensions", "tolerances", "title_block", "material", "expected_parameters"]

# Phase 0 task 2: "Use only internal or openly licensed drawings". Only these
# provenance kinds count toward the shared golden-set numbers. Client items
# are reported separately and never count (Phase 0 task 2, principle 7).
SHARED_PROVENANCE_KINDS: frozenset[str] = frozenset({"internal", "open"})

PHASE0_MIN_LABELLED_DRAWINGS = 60  # Phase 0 exit criterion
GOLDEN_DRAWINGS_RANGE = (60, 100)  # Phase 0 task 2, "60 to 100 drawings"
GOLDEN_MODELS_TARGET = 20  # Phase 0 task 2, "plus 20 STEP/STL models"

FABRIC_URI_PREFIX = "s3://"  # plan section 3, Artifact.uri: "s3:// path inside the Data Fabric"

# Leading and trailing whitespace is stripped; blank values are rejected.
NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Provenance(BaseModel):
    """Where an item comes from (Phase 0 task 2, principle 7).

    ``client_scope`` is an opaque scope tag, never a client name: client data
    stays in client scope and client names do not belong in shared assets.
    It is allowed only when ``kind`` is ``client``.
    """

    kind: Literal["internal", "open", "client"]
    licence: str | None = None  # required for openly licensed items
    client_scope: str | None = None  # required for client items, rejected for others; opaque tag only

    @model_validator(mode="after")
    def _check_kind(self) -> "Provenance":
        if self.kind == "open" and not (self.licence and self.licence.strip()):
            raise ValueError("provenance kind 'open' needs a licence")
        if self.kind == "client" and not (self.client_scope and self.client_scope.strip()):
            raise ValueError("provenance kind 'client' needs a client_scope tag")
        if self.kind != "client" and self.client_scope is not None:
            raise ValueError(f"client_scope is only allowed for provenance kind 'client', not {self.kind!r}")
        return self


def _check_fabric_uri(value: str) -> str:
    rest = value[len(FABRIC_URI_PREFIX) :]
    if not value.startswith(FABRIC_URI_PREFIX) or not rest.strip() or value != value.strip():
        raise ValueError(f"expected a Data Fabric uri starting with {FABRIC_URI_PREFIX!r}, got {value!r}")
    return value


class GoldenItem(BaseModel):
    id: NonBlankStr
    input_format: InputFormat
    part_family: NonBlankStr  # free string until OD-1 / OD-12 are decided
    provenance: Provenance
    data_uri: str  # Data Fabric location of the drawing or model
    ground_truth_uri: str | None = None  # Data Fabric location of the labels; optional until labelled
    labelled: bool = False
    label_fields: list[LabelField] = []  # labelled categories; only allowed when labelled is true

    @field_validator("data_uri")
    @classmethod
    def _data_uri(cls, v: str) -> str:
        return _check_fabric_uri(v)

    @field_validator("ground_truth_uri")
    @classmethod
    def _ground_truth_uri(cls, v: str | None) -> str | None:
        return None if v is None else _check_fabric_uri(v)

    @model_validator(mode="after")
    def _check_labels(self) -> "GoldenItem":
        dupes = sorted(f for f, n in Counter(self.label_fields).items() if n > 1)
        if dupes:
            raise ValueError(f"duplicate label_fields: {dupes}")
        if self.labelled and self.ground_truth_uri is None:
            raise ValueError(f"item {self.id!r} is labelled but has no ground_truth_uri")
        if self.labelled and not self.label_fields:
            raise ValueError(f"item {self.id!r} is labelled but lists no label_fields")
        if not self.labelled and self.label_fields:
            raise ValueError(f"item {self.id!r} is not labelled but lists label_fields")
        return self

    @property
    def is_drawing(self) -> bool:
        return self.input_format in DRAWING_FORMATS

    @property
    def is_shared(self) -> bool:
        """True for internal or openly licensed items (Phase 0 task 2)."""
        return self.provenance.kind in SHARED_PROVENANCE_KINDS


class Phase0GoldenCheck(BaseModel):
    """Golden-dataset part of the Phase 0 exit criteria.

    Only covers "golden dataset has at least 60 labelled drawings". The other
    Phase 0 exit criteria (director sign-off, CI blocks AGPL) are checked elsewhere.

    The shared counts use internal and openly licensed items only (Phase 0
    task 2). Client-scoped items appear only in the ``client_*`` fields and
    never change ``passed``.

    The 20 STEP/STL models are a task-2 target, not an exit criterion, so they
    are reported separately and do not affect ``passed``. The task-2 range of
    "60 to 100 drawings" is also reported for information only. Whether the
    range applies to all drawings or to labelled drawings is not specified in
    plan or deck; TBD in Phase 0. Both readings are reported.

    What counts as "labelled" (any one label field, or a required set of
    fields) is not specified in plan or deck; TBD in Phase 0. Here an item
    counts when ``labelled`` is true. ``labelled_drawings_by_field`` gives the
    counts per label field so a stricter rule can be applied once decided.
    """

    labelled_drawings: int  # shared (internal or open) only
    total_drawings: int  # shared only
    min_labelled_drawings: int = PHASE0_MIN_LABELLED_DRAWINGS
    drawings_range: tuple[int, int] = GOLDEN_DRAWINGS_RANGE
    total_drawings_within_range: bool  # all shared drawings in range; information only
    labelled_drawings_within_range: bool  # shared labelled drawings in range; information only
    labelled_models: int  # shared only; step + stl only
    total_models: int  # shared only; step + stl only
    models_target: int = GOLDEN_MODELS_TARGET
    models_target_met: bool
    labelled_by_format: dict[str, int]  # shared only
    labelled_drawings_by_field: dict[str, int]  # shared labelled drawings per label field
    client_labelled_drawings: int  # client-scoped; never counts toward passed
    client_labelled_models: int  # client-scoped; step + stl only
    passed: bool  # labelled_drawings >= min_labelled_drawings


class GoldenManifest(BaseModel):
    version: str
    schema_version: str = MANIFEST_SCHEMA_VERSION
    items: list[GoldenItem] = []

    @model_validator(mode="after")
    def _unique_ids(self) -> "GoldenManifest":
        dupes = sorted(i for i, n in Counter(item.id for item in self.items).items() if n > 1)
        if dupes:
            raise ValueError(f"duplicate item ids: {dupes}")
        return self

    @classmethod
    def from_json_file(cls, path: str | Path) -> "GoldenManifest":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))

    def phase0_exit_check(self) -> Phase0GoldenCheck:
        shared = [i for i in self.items if i.is_shared]
        client = [i for i in self.items if not i.is_shared]

        drawings = [i for i in shared if i.input_format in DRAWING_FORMATS]
        models = [i for i in shared if i.input_format in COUNTED_MODEL_FORMATS]
        labelled_drawings = sum(1 for i in drawings if i.labelled)
        labelled_models = sum(1 for i in models if i.labelled)
        by_format = Counter(i.input_format for i in shared if i.labelled)
        by_field = Counter(f for i in drawings if i.labelled for f in i.label_fields)
        low, high = GOLDEN_DRAWINGS_RANGE

        return Phase0GoldenCheck(
            labelled_drawings=labelled_drawings,
            total_drawings=len(drawings),
            total_drawings_within_range=low <= len(drawings) <= high,
            labelled_drawings_within_range=low <= labelled_drawings <= high,
            labelled_models=labelled_models,
            total_models=len(models),
            models_target_met=labelled_models >= GOLDEN_MODELS_TARGET,
            labelled_by_format=dict(sorted(by_format.items())),
            labelled_drawings_by_field=dict(sorted(by_field.items())),
            client_labelled_drawings=sum(1 for i in client if i.labelled and i.is_drawing),
            client_labelled_models=sum(
                1 for i in client if i.labelled and i.input_format in COUNTED_MODEL_FORMATS
            ),
            passed=labelled_drawings >= PHASE0_MIN_LABELLED_DRAWINGS,
        )

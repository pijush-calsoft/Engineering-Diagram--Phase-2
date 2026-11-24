"""Plug-in contract v0.1 (plan section 3).

Every block implements the same interface, ships as its own container, and
registers through the ``edp.blocks`` Python entry point. Breaking changes need
a new major version and an adapter.
"""

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

CONTRACT_VERSION = "0.1.0"
ENTRY_POINT_GROUP = "edp.blocks"


class SourceLocator(BaseModel):
    file_id: str                       # Data Fabric file id
    version: str                       # lakeFS commit or dataset version
    view: str | None = None            # layout, sheet, page or named view
    layer: str | None = None           # DXF layer, PDF optional content group
    handle: str | None = None          # DXF entity handle, STEP entity id, OCR region id
    bbox: tuple[float, float, float, float] | None = None  # in drawing units
    confidence: float = Field(ge=0, le=1)


class Artifact(BaseModel):
    kind: str                          # "geometry", "design_graph", "cad_script", "step", "margins", ...
    uri: str                           # s3:// path inside the Data Fabric
    schema_version: str
    sources: list[SourceLocator] = []


class Flag(BaseModel):
    code: str                          # "LOW_CONFIDENCE", "INVALID_SOLID", "UNIT_MISMATCH", ...
    message: str
    target: SourceLocator | None = None
    severity: Literal["info", "review", "block"] = "review"


class BlockRequest(BaseModel):
    run_id: str
    inputs: list[Artifact]
    params: dict = {}


class BlockResult(BaseModel):
    run_id: str
    status: Literal["ok", "needs_review", "failed"]
    outputs: list[Artifact]
    flags: list[Flag] = []
    metrics: dict = {}                 # timings, token usage, accuracy proxies


@runtime_checkable
class Block(Protocol):
    name: str
    version: str
    accepts: set[str]                  # artifact kinds it can consume
    produces: set[str]                 # artifact kinds it can emit
    def run(self, req: BlockRequest) -> BlockResult: ...


class BlockContract(BaseModel):
    """Body of ``GET /contract``: accepts, produces, schema versions (section 3)."""

    name: str
    version: str
    contract_version: str = CONTRACT_VERSION
    accepts: list[str]
    produces: list[str]
    schema_versions: dict[str, str] = {}

    @classmethod
    def of(cls, block: Block, schema_versions: dict[str, str] | None = None) -> "BlockContract":
        return cls(
            name=block.name,
            version=block.version,
            accepts=sorted(block.accepts),
            produces=sorted(block.produces),
            schema_versions=schema_versions or {},
        )

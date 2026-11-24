"""``geometry`` artifact, schema v0.1.

Source: plan Phase 2, key tasks 1 and 3. The unified geometry artifact holds
entities (line, arc, circle, spline, text, dimension), views, units, scale and
locators. The title block holds part number, revision, material, scale, units
and tolerances, with per-field confidence.

Every entity carries a required locator: the Phase 2 exit criterion is 100 %
of entities with a valid source locator.
"""

from typing import Literal

from pydantic import BaseModel

from edp_contracts.block import SourceLocator

SCHEMA_VERSION = "0.1.0"

EntityKind = Literal["line", "arc", "circle", "spline", "text", "dimension"]


class GeometryEntity(BaseModel):
    kind: EntityKind
    locator: SourceLocator
    data: dict = {}                    # kind-specific values; typed per kind in a later version


class TitleBlockField(BaseModel):
    value: str | None = None
    locator: SourceLocator             # confidence lives on the locator


class TitleBlock(BaseModel):
    part_number: TitleBlockField | None = None
    revision: TitleBlockField | None = None
    material: TitleBlockField | None = None
    scale: TitleBlockField | None = None
    units: TitleBlockField | None = None
    tolerances: TitleBlockField | None = None


class Geometry(BaseModel):
    schema_version: str = SCHEMA_VERSION
    views: list[str] = []
    units: str | None = None
    scale: str | None = None
    entities: list[GeometryEntity] = []
    title_block: TitleBlock | None = None

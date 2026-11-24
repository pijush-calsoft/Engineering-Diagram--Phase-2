"""``cad_script`` artifact, schema v0.1.

Source: plan Phase 4, Generation tasks 1, 4 and 5, and section 4.2 block 4.
Scripts are CadQuery or build123d, or OpenSCAD generated from the same design
graph. Every parameter carries a table row pointing to its source locator; the
Phase 4 exit criterion is 100 % of parameters with source locators, so the
locator is required.
"""

from typing import Literal

from pydantic import BaseModel

from edp_contracts.block import SourceLocator

SCHEMA_VERSION = "0.1.0"

ScriptLanguage = Literal["cadquery", "build123d", "openscad"]


class ScriptParameter(BaseModel):
    name: str
    value: float | int | str
    unit: str | None = None
    comment: str | None = None
    source: SourceLocator


class CadScript(BaseModel):
    schema_version: str = SCHEMA_VERSION
    language: ScriptLanguage
    code: str
    parameters: list[ScriptParameter] = []
    design_graph_uri: str | None = None

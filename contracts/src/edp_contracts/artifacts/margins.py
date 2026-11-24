"""``margins`` artifact, schema v0.1.

Source: plan Phase 5, Solver Connectors task 4 and exit criteria. A margin is
allowable over computed stress (and the equivalent for displacement, buckling
and fatigue where relevant), with the governing location as a locator on the
model. Every margin links to the solver run, the load case row and the model
version.
"""

from typing import Literal

from pydantic import BaseModel, Field, computed_field

from edp_contracts.block import SourceLocator

SCHEMA_VERSION = "0.1.0"

Quantity = Literal["stress", "displacement", "buckling", "fatigue"]


class Margin(BaseModel):
    load_case_id: str
    quantity: Quantity
    allowable: float
    computed: float = Field(gt=0)
    governing_location: SourceLocator
    solver_run_id: str
    load_case_row: SourceLocator
    model_version: str

    @computed_field  # type: ignore[prop-decorator]
    @property
    def margin(self) -> float:
        return self.allowable / self.computed


class Margins(BaseModel):
    schema_version: str = SCHEMA_VERSION
    margins: list[Margin] = []

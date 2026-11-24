"""``report`` artifact, schema v0.1.

Source: plan Phase 6, Insight tasks 1 to 3. Templates have sections for
summary, inputs, model, margins, envelope, flags and assumptions. Every number
is inserted from the Run Store by code, and the fact-check step confirms that
every numeric claim and citation resolves to the Run Store.
"""

from typing import Literal

from pydantic import BaseModel

SCHEMA_VERSION = "0.1.0"

SectionKey = Literal["summary", "inputs", "model", "margins", "envelope", "flags", "assumptions"]
ReportFormat = Literal["pdf", "docx"]


class NumericClaim(BaseModel):
    id: str
    value: float
    unit: str | None = None
    run_store_ref: str                 # pointer into the Run Store the value was read from


class ReportSection(BaseModel):
    key: SectionKey
    text: str = ""
    claim_ids: list[str] = []


class Report(BaseModel):
    schema_version: str = SCHEMA_VERSION
    run_id: str
    format: ReportFormat
    sections: list[ReportSection] = []
    claims: list[NumericClaim] = []

    def unresolved_claim_ids(self) -> set[str]:
        """Claim ids cited by a section but not present in ``claims``."""
        known = {c.id for c in self.claims}
        return {cid for s in self.sections for cid in s.claim_ids} - known

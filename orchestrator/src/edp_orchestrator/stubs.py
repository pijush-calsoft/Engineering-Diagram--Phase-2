"""Stub blocks 1 to 8 for the walking skeleton (plan Phase 1: "stub nodes for blocks 1 to 8").

Accepted and produced artifact kinds follow plan §2.1 and §3 and the outputs
named in Phases 2 to 6. Each stub copies its inputs' source locators onto its
outputs, so lineage reaches from the report back to the drawing (principle 1).
Real blocks replace these one by one through the same ``Block`` protocol.
"""

from dataclasses import dataclass, field
from typing import Literal

from edp_contracts import Artifact, BlockRequest, BlockResult, SourceLocator

INPUT_FILE_KINDS = frozenset({"dxf", "dwg", "pdf", "image", "step", "iges", "stl"})


@dataclass
class StubBlock:
    name: str
    accepts: set[str]
    produces: set[str]
    version: str = "0.0.0-stub"
    status: Literal["ok", "needs_review", "failed"] = "ok"
    calls: list[str] = field(default_factory=list)

    def run(self, req: BlockRequest) -> BlockResult:
        self.calls.append(req.run_id)
        sources: list[SourceLocator] = []
        for a in req.inputs:
            sources.extend(s for s in a.sources if s not in sources)
        outputs = [
            Artifact(
                kind=k, uri=f"stub://{req.run_id}/{self.name}/{k}", schema_version="stub", sources=sources
            )
            for k in sorted(self.produces)
        ]
        return BlockResult(run_id=req.run_id, status=self.status, outputs=outputs, metrics={"stub": True})


def stub_blocks() -> list[StubBlock]:
    """The R1 pipeline as stubs, in pipeline order (plan §2.1)."""
    return [
        StubBlock("b1_parser", set(INPUT_FILE_KINDS), {"geometry"}),
        StubBlock("b2_interpretation", {"geometry"}, {"design_graph"}),
        StubBlock("b3_knowledge_graph", {"design_graph"}, {"similar_parts"}),
        StubBlock("b4_generation", {"design_graph"}, {"cad_script"}),
        StubBlock("b5_opencad", {"cad_script"}, {"step"}),
        StubBlock("b6_solvers", {"step"}, {"margins"}),
        StubBlock("b7_surrogate", {"margins"}, {"envelope"}),
        StubBlock("b8_report", {"margins", "envelope"}, {"report"}),
    ]

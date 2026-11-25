"""Walking skeleton (plan Phase 1 exit criteria, without the container-only services; ADR-0008)."""

import io
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from edp_catalogue import Catalogue
from edp_contracts import BlockRequest, BlockResult
from edp_contracts.events import (
    CATALOGUE_LINEAGE_RECORDED,
    FABRIC_DATASET_VERSIONED,
    FABRIC_FILE_INGESTED,
    RUN_BLOCK_COMPLETED,
    RUN_BLOCK_FAILED,
    RUN_BLOCK_STARTED,
    RUN_PLANNED,
)
from edp_eval.synth.dxf_writer import generate
from edp_eval.synth.profiles import PROFILES
from edp_fabric import FabricStore, IngestResult
from edp_kit import InMemoryEventBus
from edp_orchestrator import Orchestrator, StubBlock, stub_blocks

PIPELINE = [
    "b1_parser",
    "b2_interpretation",
    "b3_knowledge_graph",
    "b4_generation",
    "b5_opencad",
    "b6_solvers",
    "b7_surrogate",
    "b8_report",
]


@dataclass
class Env:
    root: Path
    bus: InMemoryEventBus = field(default_factory=InMemoryEventBus)

    def __post_init__(self) -> None:
        self.fabric = FabricStore(self.root / "fabric", self.bus)
        self.catalogue = Catalogue(self.root / "catalogue.sqlite", self.bus)

    def orchestrator(self, blocks) -> Orchestrator:
        return Orchestrator(blocks, self.catalogue, self.bus, self.root / "checkpoints.sqlite")

    def upload(self) -> IngestResult:
        doc, _ = generate(PROFILES["asme"], "bracket", 3, seed=5)
        buf = io.StringIO()
        doc.write(buf)
        return self.fabric.ingest("bracket.dxf", buf.getvalue().encode("utf-8"), uploader="engineer")


class CrashOnce(StubBlock):
    def run(self, req: BlockRequest) -> BlockResult:
        if not self.calls:
            self.calls.append("crashed")
            raise RuntimeError("simulated crash")
        return super().run(req)


def test_upload_to_eight_stub_results_with_lineage(tmp_path):
    env = Env(tmp_path)
    upload = env.upload()
    status = env.orchestrator(stub_blocks()).start("run-1", [upload.as_artifact()])

    assert status.state == "completed" and status.error is None
    assert [r["block"] for r in status.results] == PIPELINE
    # Versioned dataset in the Fabric
    assert env.bus.subjects()[:2] == [FABRIC_FILE_INGESTED, FABRIC_DATASET_VERSIONED]
    # Events: planned, then started/completed and lineage for each block
    subjects = env.bus.subjects()
    assert subjects.count(RUN_PLANNED) == 1
    assert subjects.count(RUN_BLOCK_STARTED) == subjects.count(RUN_BLOCK_COMPLETED) == 8
    assert subjects.count(CATALOGUE_LINEAGE_RECORDED) == 8
    # Lineage: the report traces back to the uploaded drawing version
    report = [r for r in env.catalogue.by_run("run-1") if r.artifact.kind == "report"]
    assert len(report) == 1
    src = env.catalogue.lineage(report[0].id)
    assert [(s.file_id, s.version) for s in src] == [(upload.file_id, upload.commit)]
    assert len(env.catalogue.derived_from(upload.file_id)) == 8


def test_restart_mid_run_resumes_from_checkpoint(tmp_path):
    env = Env(tmp_path)
    upload = env.upload()
    blocks = stub_blocks()
    blocks[4] = CrashOnce("b5_opencad", {"cad_script"}, {"step"})
    first = env.orchestrator(blocks).start("run-2", [upload.as_artifact()])
    assert (
        first.state == "stopped" and first.next == ["b5_opencad"] and "simulated crash" in (first.error or "")
    )
    assert RUN_BLOCK_FAILED in env.bus.subjects()

    # A new orchestrator instance on the same checkpoint store stands in for a process restart.
    resumed = env.orchestrator(blocks).resume("run-2")
    assert resumed.state == "completed"
    assert [r["block"] for r in resumed.results] == PIPELINE
    assert all(len(b.calls) == 1 for i, b in enumerate(blocks) if i != 4)  # blocks 1-4 not re-run


def test_needs_review_pauses_until_a_reviewer_decides(tmp_path):
    env = Env(tmp_path)
    upload = env.upload()
    blocks = stub_blocks()
    blocks[1].status = "needs_review"
    orch = env.orchestrator(blocks)

    paused = orch.start("run-3", [upload.as_artifact()])
    assert paused.state == "awaiting_review"
    assert [r["block"] for r in paused.results] == PIPELINE[:2] and blocks[2].calls == []

    done = orch.review("run-3", "approve", reviewer="design-lead")
    assert done.state == "completed" and len(done.results) == 8
    with pytest.raises(ValueError):
        orch.review("run-3", "approve", reviewer="design-lead")


def test_rejected_review_stops_the_run(tmp_path):
    env = Env(tmp_path)
    blocks = stub_blocks()
    blocks[0].status = "needs_review"
    orch = env.orchestrator(blocks)
    orch.start("run-4", [env.upload().as_artifact()])
    rejected = orch.review("run-4", "reject", reviewer="design-lead")
    assert rejected.state == "rejected" and len(rejected.results) == 1


def test_run_ids_are_unique(tmp_path):
    env = Env(tmp_path)
    orch = env.orchestrator(stub_blocks())
    art = env.upload().as_artifact()
    orch.start("run-5", [art])
    with pytest.raises(ValueError):
        orch.start("run-5", [art])

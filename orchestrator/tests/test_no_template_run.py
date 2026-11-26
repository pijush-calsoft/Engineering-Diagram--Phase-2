"""A construction run on a drawing no template matches (found 2026-11-26 with a plan exported
from another BIM tool). Block 4 flags NO_TEMPLATE for a person; once approved, blocks 5 to 8
pass the run through (ADR-0010) instead of the run stopping for want of a cad_script.
Needs no CalculiX or Gmsh: block 6 is skipped."""

import io

from edp_catalogue import Catalogue
from edp_contracts.registry import discover_blocks
from edp_eval.synth.dxf_writer import generate
from edp_eval.synth.profiles import PROFILES
from edp_fabric import FabricStore
from edp_kit import InMemoryEventBus
from edp_orchestrator import Orchestrator, stub_blocks

DOMAIN_BLOCKS = ("b5_opencad", "b6_solvers", "b8_report")


def bracket_dxf() -> bytes:
    doc, _ = generate(PROFILES["iso"], "bracket", 0, 1)
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode()


def test_no_template_run_passes_through_after_approval(tmp_path, monkeypatch):
    monkeypatch.setenv("EDP_DATA_DIR", str(tmp_path))
    bus = InMemoryEventBus()
    fabric = FabricStore(tmp_path / "fabric", bus)
    catalogue = Catalogue(tmp_path / "catalogue.sqlite", bus)
    real = discover_blocks()
    blocks = [real.get(b.name, b) for b in stub_blocks()]
    orch = Orchestrator(blocks, catalogue, bus, tmp_path / "cp.sqlite")
    up = fabric.ingest("bracket.dxf", bracket_dxf(), uploader="test")

    status = orch.start("run-nt", [up.as_artifact()], {"domain_pack": "construction"})
    assert status.state == "awaiting_review" and status.results[-1]["block"] == "b4_generation"
    assert [f["code"] for f in status.results[-1]["flags"]] == ["NO_TEMPLATE"]

    status = orch.review("run-nt", "approve", "design-lead")
    assert status.state == "completed"
    by_block = {r["block"]: r for r in status.results}
    for name in DOMAIN_BLOCKS:
        assert by_block[name]["status"] == "ok"
        assert [f["code"] for f in by_block[name]["flags"]] == ["SKIPPED"]

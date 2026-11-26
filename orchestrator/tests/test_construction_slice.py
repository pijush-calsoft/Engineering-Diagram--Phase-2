"""End to end: a construction base-plate drawing through every real block (owner direction
2026-11-26; deck slide 85 Demo 4: drawing to editable model, simulation evidence, margin and
report). Skipped where CalculiX or Gmsh is not installed (setup guide)."""

import io
import random

import pytest
from docx import Document

from edp_b6_solvers import calculix
from edp_catalogue import Catalogue
from edp_contracts.artifacts.margins import Margins
from edp_contracts.artifacts.report import Report
from edp_contracts.registry import discover_blocks
from edp_eval.synth.construction import sample_base_plate
from edp_eval.synth.dxf_writer import generate
from edp_eval.synth.parts import Hole, Plate
from edp_eval.synth.profiles import PROFILES
from edp_fabric import FabricStore
from edp_kit import InMemoryEventBus
from edp_orchestrator import Orchestrator, stub_blocks

pytestmark = pytest.mark.skipif(
    calculix.ccx_path() is None or calculix.gmsh_python() is None, reason="CalculiX or Gmsh not installed"
)


def small_base_plate_dxf() -> bytes:
    # A small plate keeps the mesh and solver run short; the sampler's rules still hold.
    sample_base_plate(random.Random(0))  # the family sampler works; this test fixes its own sizes
    holes = tuple(Hole(x, y, 22.0) for y in (50.0, 200.0) for x in (50.0, 200.0))
    part = Plate(250.0, 250.0, 25.0, holes)
    doc, _ = generate(
        PROFILES["iso"],
        "base_plate",
        0,
        1,
        part=part,
        title={"part_number": "EDP-BP-TEST", "material": "S355J2"},
    )
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode()


def test_base_plate_runs_from_drawing_to_signed_report(tmp_path, monkeypatch):
    monkeypatch.setenv("EDP_DATA_DIR", str(tmp_path))
    bus = InMemoryEventBus()
    fabric = FabricStore(tmp_path / "fabric", bus)
    catalogue = Catalogue(tmp_path / "catalogue.sqlite", bus)
    real = discover_blocks()
    blocks = [real.get(b.name, b) for b in stub_blocks()]
    orch = Orchestrator(blocks, catalogue, bus, tmp_path / "cp.sqlite")
    up = fabric.ingest("bp.dxf", small_base_plate_dxf(), uploader="test")

    status = orch.start("run-bp", [up.as_artifact()], {"domain_pack": "construction"})
    # A 25 mm plate carries the illustrative load (margin above one), so block 6 records the
    # illustrative-load flag without stopping; the run stops only for report sign-off.
    b6 = next(r for r in status.results if r["block"] == "b6_solvers")
    assert "ILLUSTRATIVE_LOAD" in {f["code"] for f in b6["flags"]}
    assert status.state == "awaiting_review" and status.results[-1]["block"] == "b8_report"
    assert [f["code"] for f in status.results[-1]["flags"]] == ["SIGN_OFF_REQUIRED"]
    status = orch.review("run-bp", "approve", "design-lead")
    assert status.state == "completed"

    records = {r.artifact.kind: r.artifact for r in catalogue.by_run("run-bp")}
    margins = Margins.model_validate_json(fabric.read(records["margins"].uri)).margins
    assert margins and margins[0].allowable == 345.0  # S355J2, 16 < t <= 40 mm (EN 10025-2)
    assert margins[0].load_case_row.handle == "BP-UPLIFT-ILLUSTRATIVE"
    report = Report.model_validate_json(fabric.read(records["report"].uri))
    assert report.claims and not report.unresolved_claim_ids()
    text = "\n".join(p.text for p in Document(io.BytesIO(fabric.read(records["docx"].uri))).paragraphs)
    assert "EDP-BP-TEST" in text and "DRAFT: not signed off" in text
    assert records["report"].sources[0].file_id == up.file_id  # the report traces back to the drawing


def wait_for(client, run_id: str, seconds: float = 900.0) -> dict:
    import time

    end = time.monotonic() + seconds
    while time.monotonic() < end:
        view = client.get(f"/api/runs/{run_id}").json()
        if not view["running"]:
            return view
        time.sleep(0.5)
    raise AssertionError(f"run {run_id} did not finish")


def test_console_shows_model_and_report_and_reruns_with_a_changed_thickness(tmp_path):
    # Demo 4 in the console (deck slide 85): model, margin and report on screen, then a person
    # changes the thickness and the model, simulation and report follow in a new run.
    from fastapi.testclient import TestClient

    from edp_orchestrator.server import Console, create_app

    console = Console(tmp_path / "data")
    c = TestClient(create_app(console))
    upload = {"file": ("bp.dxf", small_base_plate_dxf())}
    first = c.post("/api/runs", params={"domain_pack": "construction"}, files=upload).json()["run_id"]
    view = wait_for(c, first)
    assert view["status"]["state"] == "awaiting_review" and view["domain_pack"] == "construction"
    model = c.get(f"/api/runs/{first}/model").json()
    assert model["indices"] and model["bbox"][5] - model["bbox"][2] == pytest.approx(25.0, abs=0.01)
    docx = c.get(f"/api/runs/{first}/report.docx")
    assert docx.status_code == 200 and docx.content[:2] == b"PK"

    assert c.post(f"/api/runs/{first}/rerun", json={"overrides": {"length": 300}}).status_code == 422
    assert c.post("/api/runs/run-none/rerun", json={"overrides": {"thickness": 12}}).status_code == 404
    second = c.post(f"/api/runs/{first}/rerun", json={"overrides": {"thickness": 12}}).json()["run_id"]
    view = wait_for(c, second)
    assert view["parent"] == first and view["overrides"] == {"thickness": 12.0}
    # A 12 mm plate does not carry the illustrative load: block 6 stops for a person first.
    b6 = view["status"]["results"][-1]
    assert b6["block"] == "b6_solvers" and "MARGIN_BELOW_ONE" in {f["code"] for f in b6["flags"]}
    c.post(f"/api/runs/{second}/review", json={"decision": "approve", "reviewer": "design lead"})
    view = wait_for(c, second)
    assert view["status"]["results"][-1]["block"] == "b8_report"
    assert view["status"]["state"] == "awaiting_review"  # report written, fact check passed
    model = c.get(f"/api/runs/{second}/model").json()
    assert model["bbox"][5] - model["bbox"][2] == pytest.approx(12.0, abs=0.01)
    kinds = {a["kind"]: a["uri"] for a in view["artifacts"] if a["uri"].startswith("fabric://")}
    margins = c.get("/api/artifact", params={"uri": kinds["margins"]}).json()["margins"]
    assert margins[0]["allowable"] == 355.0  # S355J2, t <= 16 mm: the yield band follows the change
    report = Report.model_validate(c.get("/api/artifact", params={"uri": kinds["report"]}).json())
    inputs = next(s.text for s in report.sections if s.key == "inputs")
    assert (
        "Length and width read from the drawing's dimensions; "
        "thickness set to 12 mm for this run, where the drawing says 25 mm"
    ) in inputs
    assert any(c.run_store_ref == "run_params:/overrides/thickness" for c in report.claims)
    flags_text = next(s.text for s in report.sections if s.key == "flags")
    assert "must be revised" in flags_text
    runs = {r["run_id"]: r for r in c.get("/api/runs").json()}
    assert runs[second]["parent"] == first and runs[first]["overrides"] == {}

import io
from pathlib import Path

import ezdxf
import pytest

from edp_b1_parser import DrawingParser, dxf
from edp_catalogue import Catalogue
from edp_contracts import Artifact, Block, BlockRequest, SourceLocator
from edp_contracts.artifacts.geometry import Geometry
from edp_contracts.registry import discover_blocks
from edp_eval.metrics import Dimension, dimension_f1
from edp_eval.suites.parser_dxf import evaluate_drawing, run
from edp_eval.synth import write_set
from edp_eval.synth.labels import SyntheticLabel
from edp_fabric import FabricStore
from edp_kit import InMemoryEventBus
from edp_orchestrator import Orchestrator, stub_blocks


def to_bytes(doc, crlf: bool = False) -> bytes:
    buf = io.StringIO()
    doc.write(buf)
    text = buf.getvalue()
    return (text.replace("\n", "\r\n") if crlf else text).encode("utf-8")


def new_doc(units: int = 4):
    doc = ezdxf.new("R2010", setup=True, units=units)
    return doc, doc.modelspace()


def parse(doc, crlf: bool = False):
    return dxf.parse(to_bytes(doc, crlf), "file-1", "commit-1")


def test_reads_dimension_value_handle_and_bbox():
    doc, msp = new_doc()
    msp.add_line((0, 0), (80, 0))
    dim = msp.add_linear_dim(base=(0, -10), p1=(0, 0), p2=(80, 0), dimstyle="EZDXF", override={"dimlfac": 1})
    dim.render()
    g, flags, m = parse(doc, crlf=True)  # CRLF files must parse (bug found in Phase 2)
    d = next(e for e in g.entities if e.kind == "dimension")
    assert d.locator.handle == dim.dimension.dxf.handle and d.data["value"] == 80.0
    assert d.data["dimtype"] == "linear" and d.locator.bbox is not None
    assert (d.locator.file_id, d.locator.version, d.locator.view) == ("file-1", "commit-1", "Model")
    assert g.units == "mm" and flags == [] and m["dimensions"] == 1


def test_overridden_dimension_text_is_reported_and_flagged():
    doc, msp = new_doc()
    dim = msp.add_linear_dim(
        base=(0, -10), p1=(0, 0), p2=(80, 0), text="85", dimstyle="EZDXF", override={"dimlfac": 1}
    )
    dim.render()
    g, flags, _ = parse(doc)
    d = next(e for e in g.entities if e.kind == "dimension")
    assert d.data["value"] == 85.0 and d.data["measurement"] == 80.0
    assert [f.code for f in flags] == ["DIM_TEXT_MISMATCH"] and flags[0].target.handle == d.locator.handle


def test_title_block_conflict_lowers_confidence_and_flags():
    doc, msp = new_doc()
    msp.add_text("MATERIAL: S235JR")
    msp.add_text("MATL: 1.4301")
    msp.add_text("REV: B")
    g, flags, _ = parse(doc)
    assert g.title_block.revision.value == "B" and g.title_block.revision.locator.confidence == 1.0
    assert g.title_block.material.locator.confidence == 0.5
    assert [f.code for f in flags] == ["LOW_CONFIDENCE"]


def test_unit_mismatch_between_title_block_and_header():
    doc, msp = new_doc(units=4)
    msp.add_text("UNITS: INCHES")
    _, flags, _ = parse(doc)
    assert [f.code for f in flags] == ["UNIT_MISMATCH"]
    doc2, msp2 = new_doc(units=4)
    msp2.add_text("UNITS: millimetres")
    assert parse(doc2)[1] == []


def test_blocks_polylines_and_layouts_are_resolved_with_source_handles():
    doc, msp = new_doc()
    blk = doc.blocks.new("BOLT")
    blk.add_circle((0, 0), 3)
    blk.add_line((-3, 0), (3, 0))
    insert = msp.add_blockref("BOLT", (10, 10))
    poly = msp.add_lwpolyline([(0, 0), (20, 0), (20, 5)])
    paper = doc.layouts.get("Layout1")
    note = paper.add_text("NOTE: DEBURR ALL EDGES")
    g, _, _ = parse(doc)
    from_insert = [e for e in g.entities if e.locator.handle == insert.dxf.handle]
    assert sorted(e.kind for e in from_insert) == ["circle", "line"]
    assert from_insert[0].data["from"] == "block BOLT"
    assert [e.kind for e in g.entities if e.locator.handle == poly.dxf.handle] == ["line", "line"]
    assert any(e.locator.handle == note.dxf.handle and e.locator.view == "Layout1" for e in g.entities)
    assert g.views == ["Model", "Layout1"]


def test_unsupported_entities_are_counted_not_guessed():
    doc, msp = new_doc()
    msp.add_point((1, 1))
    msp.add_ellipse((0, 0), major_axis=(5, 0), ratio=0.5)
    g, flags, m = parse(doc)
    assert g.entities == [] and m["skipped"] == {"POINT": 1, "ELLIPSE": 1}
    assert flags[0].code == "UNSUPPORTED_ENTITY" and flags[0].severity == "info"


def test_block_writes_geometry_to_the_cleaned_zone(tmp_path):
    fabric = FabricStore(tmp_path)
    doc, msp = new_doc()
    msp.add_text("PART NO: X-1")
    up = fabric.ingest("x.dxf", to_bytes(doc), uploader="t")
    parser = DrawingParser(fabric)
    assert isinstance(parser, Block)
    result = parser.run(BlockRequest(run_id="r1", inputs=[up.as_artifact()]))
    out = result.outputs[0]
    assert result.status == "ok" and out.uri.startswith("fabric://cleaned/run-r1/")
    assert out.sources[0].file_id == up.file_id
    geometry = Geometry.model_validate_json(fabric.read(out.uri))
    assert geometry.title_block.part_number.value == "X-1"


def test_needs_review_when_flags_need_review(tmp_path):
    fabric = FabricStore(tmp_path)
    doc, msp = new_doc()
    msp.add_text("UNITS: IN")
    up = fabric.ingest("x.dxf", to_bytes(doc), uploader="t")
    assert (
        DrawingParser(fabric).run(BlockRequest(run_id="r1", inputs=[up.as_artifact()])).status
        == "needs_review"
    )


def test_registered_through_the_entry_point(tmp_path, monkeypatch):
    monkeypatch.setenv("EDP_DATA_DIR", str(tmp_path))
    blocks = discover_blocks()
    assert isinstance(blocks["b1_parser"], DrawingParser)
    with pytest.raises(ValueError):
        loc = SourceLocator(file_id="f", version="v", confidence=1)
        blocks["b1_parser"].run(
            BlockRequest(
                run_id="r", inputs=[Artifact(kind="dxf", uri="s3://x", schema_version="file", sources=[loc])]
            )
        )


def test_real_parser_in_the_orchestrator(tmp_path):
    bus = InMemoryEventBus()
    fabric = FabricStore(tmp_path / "fabric", bus)
    write_set(tmp_path / "golden", 1, seed=3, uri_prefix="s3://edp-fabric/golden")
    path = next((tmp_path / "golden").glob("*.dxf"))
    up = fabric.ingest(path.name, path.read_bytes(), uploader="t")
    blocks = stub_blocks()
    blocks[0] = DrawingParser(fabric)
    orch = Orchestrator(blocks, Catalogue(tmp_path / "c.sqlite", bus), bus, tmp_path / "cp.sqlite")
    status = orch.start("run-p", [up.as_artifact()])
    assert status.state == "completed" and status.results[0]["block"] == "b1_parser"
    assert status.results[0]["metrics"]


def test_suite_scores_the_golden_set_and_can_fail(tmp_path):
    write_set(tmp_path, 4, seed=9, uri_prefix="s3://edp-fabric/golden")
    report = run(tmp_path, value_tol=1e-6, n_bins=10)
    assert report["drawings"] == 4 and report["overall"]["dimension_f1"] == 1.0
    # A wrong label must lower the score: the suite is not a tautology.
    label_path = next(tmp_path.glob("*.labels.json"))
    label = SyntheticLabel.model_validate_json(label_path.read_text(encoding="utf-8"))
    label.dimensions[0].value += 1.0
    label.title_block["material"].value = "WRONG"
    c = evaluate_drawing(Path(tmp_path / f"{label.id}.dxf"), label, value_tol=1e-6)
    assert c.tp == c.n_truth - 1 and c.tb_correct == c.tb_total - 1
    assert (
        dimension_f1([Dimension(target="a", value=1)], [Dimension(target="b", value=1)], value_tol=1).f1 == 0
    )


@pytest.mark.parametrize(
    ("measured_to", "text", "flagged"), [(80.4, "80", False), (80.6, "80", True), (2.9534, "2.953", False)]
)
def test_rounded_display_is_not_a_mismatch(measured_to, text, flagged):
    doc, msp = new_doc()
    dim = msp.add_linear_dim(
        base=(0, -10), p1=(0, 0), p2=(measured_to, 0), text=text, dimstyle="EZDXF", override={"dimlfac": 1}
    )
    dim.render()
    _, flags, _ = parse(doc)
    assert (flags != []) is flagged

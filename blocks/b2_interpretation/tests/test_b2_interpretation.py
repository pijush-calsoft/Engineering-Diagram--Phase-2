import io

import ezdxf
import pytest

from edp_b1_parser import DrawingParser, dxf
from edp_b2_interpretation import Interpretation, interpret, to_mm
from edp_catalogue import Catalogue
from edp_contracts import Block, BlockRequest
from edp_contracts.artifacts.design_graph import DesignGraph
from edp_contracts.registry import discover_blocks
from edp_eval.suites.interpretation import evaluate_drawing, run
from edp_eval.synth import write_set
from edp_eval.synth.labels import SyntheticLabel
from edp_fabric import FabricStore
from edp_kit import InMemoryEventBus
from edp_orchestrator import Orchestrator, stub_blocks

DIM = {"dimstyle": "EZDXF", "override": {"dimlfac": 1}}


def plate(units: int = 4):
    doc = ezdxf.new("R2010", setup=True, units=units)
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (100, 0), (100, 50), (0, 50)], close=True)
    return doc, msp


def graph_of(doc) -> tuple[DesignGraph, list, dict]:
    buf = io.StringIO()
    doc.write(buf)
    g, _, _ = dxf.parse(buf.getvalue().encode(), "f", "c")
    return interpret(g)


def params(graph: DesignGraph, feature: str) -> dict[str, dict]:
    nodes = {n.id: n for n in graph.nodes}
    return {
        nodes[e.target].attributes["name"]: nodes[e.target].attributes
        for e in graph.edges
        if e.source == feature
    }


def test_dimensioned_hole_is_geometric_with_locators():
    doc, msp = plate()
    msp.add_circle((20, 15), 3)
    msp.add_diameter_dim(
        center=(20, 15), radius=3, angle=45, dimstyle="EZ_RADIUS", override={"dimlfac": 1}
    ).render()
    msp.add_linear_dim(base=(0, -10), p1=(0, 0), p2=(20, 15), angle=0, **DIM).render()
    msp.add_linear_dim(base=(-10, 0), p1=(0, 0), p2=(20, 15), angle=90, **DIM).render()
    graph, flags, m = graph_of(doc)
    p = params(graph, "hole1")
    assert flags == [] and m["features"] == {"hole": 1}
    assert {k: (v["value"], v["association"]) for k, v in p.items()} == {
        "diameter": (6.0, "geometric"),
        "x": (20.0, "geometric"),
        "y": (15.0, "geometric"),
    }
    node = next(n for n in graph.nodes if n.id == "hole1.diameter")
    assert len(node.sources) >= 2 and all(s.confidence == 1.0 for s in node.sources)


def test_undimensioned_hole_is_low_confidence_with_reason():
    doc, msp = plate()
    msp.add_circle((20, 15), 3)
    graph, flags, _ = graph_of(doc)
    p = params(graph, "hole1")
    assert p["diameter"]["association"] == "geometry_only" and p["diameter"]["confidence"] == 0.7
    assert {f.code for f in flags} == {"LOW_CONFIDENCE"}
    assert all("[UNDIMENSIONED]" in f.message for f in flags) and len(flags) == 3


def test_contradicting_dimensions_are_flagged():
    doc, msp = plate()
    msp.add_circle((20, 15), 3)
    for text in ("6", "7"):
        msp.add_diameter_dim(
            center=(20, 15), radius=3, angle=45, text=text, dimstyle="EZ_RADIUS", override={"dimlfac": 1}
        ).render()
    _, flags, _ = graph_of(doc)
    assert "CONTRADICTION" in {f.code for f in flags}


def test_hole_without_outline_and_hole_outside_outline():
    doc = ezdxf.new("R2010", setup=True, units=4)
    doc.modelspace().add_circle((5, 5), 2)
    _, flags, _ = graph_of(doc)
    assert any("[NO_DATUM]" in f.message for f in flags)
    doc2, msp2 = plate()
    msp2.add_circle((99, 25), 3)
    _, flags2, _ = graph_of(doc2)
    assert "FEATURE_OUTSIDE_PART" in {f.code for f in flags2}


def test_vertical_slot_and_bend():
    doc, msp = plate()
    msp.add_arc((50, 10), 4, 180, 360)  # bottom end, opens upward
    msp.add_arc((50, 30), 4, 0, 180)  # top end
    msp.add_linear_dim(base=(70, 0), p1=(50, 6), p2=(50, 34), angle=90, **DIM).render()
    msp.add_arc((200, 200), 2, 180, 270)
    msp.add_arc((200, 200), 5, 180, 270)
    graph, _, m = graph_of(doc)
    assert m["features"] == {"bend": 1, "slot": 1}
    assert params(graph, "slot1")["length"]["value"] == 28.0
    assert params(graph, "slot1")["length"]["association"] == "geometric"
    bend = params(graph, "bend1")
    assert (bend["radius"]["value"], bend["thickness"]["value"]) == (2.0, 3.0)


def test_units_are_normalised_with_pint_and_missing_units_flagged():
    assert to_mm(2.5, "in") == pytest.approx(63.5) and to_mm(1, "m") == 1000 and to_mm(1, None) is None
    doc, msp = plate(units=1)
    msp.add_circle((2, 1), 0.125)
    graph, _, _ = graph_of(doc)
    assert params(graph, "hole1")["diameter"]["value_mm"] == pytest.approx(6.35)
    doc0, msp0 = plate(units=0)
    msp0.add_circle((20, 15), 3)
    _, flags, _ = graph_of(doc0)
    assert any("[UNITS_UNKNOWN]" in f.message for f in flags)


def test_material_and_tolerance_nodes_from_the_title_block():
    doc, msp = plate()
    msp.add_text("MATERIAL: S235JR")
    msp.add_text("TOLERANCES: ISO 2768-m")
    graph, _, _ = graph_of(doc)
    kinds = {n.id: (n.kind, n.attributes) for n in graph.nodes}
    assert kinds["material"] == ("material", {"name": "S235JR"})
    assert kinds["general_tolerance"][0] == "tolerance"


def test_parser_and_interpretation_in_the_orchestrator(tmp_path, monkeypatch):
    monkeypatch.setenv("EDP_DATA_DIR", str(tmp_path))
    assert isinstance(discover_blocks()["b2_interpretation"], Interpretation)
    bus = InMemoryEventBus()
    fabric = FabricStore(tmp_path / "fabric", bus)
    write_set(tmp_path / "golden", 2, seed=4, uri_prefix="s3://edp-fabric/golden")
    path = sorted((tmp_path / "golden").glob("*.dxf"))[0]
    up = fabric.ingest(path.name, path.read_bytes(), uploader="t")
    blocks: list[Block] = list(stub_blocks())
    blocks[0], blocks[1] = DrawingParser(fabric), Interpretation(fabric)
    orch = Orchestrator(blocks, Catalogue(tmp_path / "c.sqlite", bus), bus, tmp_path / "cp.sqlite")
    status = orch.start("run-i", [up.as_artifact()])
    assert status.state == "completed" and [r["block"] for r in status.results][:2] == [
        "b1_parser",
        "b2_interpretation",
    ]
    graph_art = next(
        r for r in Catalogue(tmp_path / "c.sqlite").by_run("run-i") if r.artifact.kind == "design_graph"
    )
    graph = DesignGraph.model_validate_json(fabric.read(graph_art.artifact.uri))
    assert any(n.kind == "feature" for n in graph.nodes)
    assert graph_art.artifact.sources[0].file_id == up.file_id


def test_low_confidence_goes_to_the_knowledge_graph_not_to_review(tmp_path):
    fabric = FabricStore(tmp_path)
    doc, msp = plate()
    msp.add_circle((20, 15), 3)
    buf = io.StringIO()
    doc.write(buf)
    up = fabric.ingest("p.dxf", buf.getvalue().encode(), uploader="t")
    geo = DrawingParser(fabric).run(BlockRequest(run_id="r", inputs=[up.as_artifact()])).outputs
    result = Interpretation(fabric).run(BlockRequest(run_id="r", inputs=geo))
    # Plan principle 3: low-confidence values are passed on for corroboration (block 3).
    assert result.status == "ok" and result.outputs[0].kind == "design_graph"
    assert {f.code for f in result.flags} == {"LOW_CONFIDENCE"}
    # A contradiction still needs a person.
    doc2, msp2 = plate()
    msp2.add_circle((20, 15), 3)
    for text in ("6", "7"):
        msp2.add_diameter_dim(
            center=(20, 15), radius=3, angle=45, text=text, dimstyle="EZ_RADIUS", override={"dimlfac": 1}
        ).render()
    buf2 = io.StringIO()
    doc2.write(buf2)
    up2 = fabric.ingest("q.dxf", buf2.getvalue().encode(), uploader="t")
    geo2 = DrawingParser(fabric).run(BlockRequest(run_id="r2", inputs=[up2.as_artifact()])).outputs
    assert Interpretation(fabric).run(BlockRequest(run_id="r2", inputs=geo2)).status == "needs_review"


def test_suite_scores_and_can_fail(tmp_path):
    write_set(tmp_path, 4, seed=8, uri_prefix="s3://edp-fabric/golden")
    report = run(tmp_path, value_tol=1e-6)
    assert report["overall"]["feature_recall"] == 1.0 and report["phase3_feature_target_met"]
    label_path = next(tmp_path.glob("*plate*.labels.json"))
    label = SyntheticLabel.model_validate_json(label_path.read_text(encoding="utf-8"))
    label.features[0].parameters["diameter"] += 1.0
    r = evaluate_drawing(tmp_path / f"{label.id}.dxf", label, value_tol=1e-6)
    assert r["matched"] == r["truth_features"] - 1

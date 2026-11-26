import json

import pytest
from pydantic import ValidationError

from edp_contracts import SourceLocator
from edp_contracts.artifacts import ARTIFACT_MODELS
from edp_contracts.artifacts.cad_script import CadScript, ScriptParameter
from edp_contracts.artifacts.design_graph import DesignEdge, DesignGraph, DesignNode
from edp_contracts.artifacts.geometry import Geometry, GeometryEntity, TitleBlock, TitleBlockField
from edp_contracts.artifacts.margins import Margin, Margins
from edp_contracts.artifacts.report import NumericClaim, Report, ReportSection
from edp_contracts.export import all_schemas, write_schemas


def loc(**kw) -> SourceLocator:
    return SourceLocator(**{"file_id": "f1", "version": "c1", "confidence": 0.8, **kw})


def test_geometry_entities_require_a_locator():
    with pytest.raises(ValidationError):
        GeometryEntity(kind="line")
    with pytest.raises(ValidationError):
        GeometryEntity(kind="polyline", locator=loc())
    g = Geometry(
        views=["front"],
        units="mm",
        entities=[GeometryEntity(kind="dimension", locator=loc(handle="2F"), data={"value": 32.0})],
        title_block=TitleBlock(material=TitleBlockField(value="S355", locator=loc(confidence=0.6))),
    )
    assert g.title_block.material.locator.confidence == 0.6


def test_design_graph_feature_type_rules():
    DesignNode(id="h1", kind="feature", feature_type="hole")
    with pytest.raises(ValidationError):
        DesignNode(id="h1", kind="feature")
    with pytest.raises(ValidationError):
        DesignNode(id="p1", kind="parameter", feature_type="hole")


def test_design_graph_edges_must_reference_nodes():
    nodes = [DesignNode(id="h1", kind="feature", feature_type="hole"), DesignNode(id="d1", kind="parameter")]
    DesignGraph(nodes=nodes, edges=[DesignEdge(source="h1", target="d1", relation="has")])
    with pytest.raises(ValidationError):
        DesignGraph(nodes=nodes, edges=[DesignEdge(source="h1", target="zz", relation="has")])
    with pytest.raises(ValidationError):
        DesignGraph(nodes=nodes + [DesignNode(id="h1", kind="datum")])


def test_cad_script_parameters_require_a_source():
    with pytest.raises(ValidationError):
        ScriptParameter(name="width", value=40)
    param = ScriptParameter(name="w", value=40, source=loc())
    s = CadScript(language="cadquery", code="...", parameters=[param])
    assert s.parameters[0].source.file_id == "f1"
    with pytest.raises(ValidationError):
        CadScript(language="freecad", code="...")


def test_margin_is_allowable_over_computed_and_serialised():
    m = Margin(
        load_case_id="LC1",
        quantity="stress",
        allowable=300.0,
        computed=200.0,
        governing_location=loc(handle="node-17"),
        solver_run_id="run-9",
        load_case_row=loc(file_id="loads.csv", handle="row-3"),
        model_version="v1",
    )
    assert m.margin == pytest.approx(1.5)
    assert Margins(margins=[m]).model_dump()["margins"][0]["margin"] == pytest.approx(1.5)
    with pytest.raises(ValidationError):
        Margin(**{**m.model_dump(exclude={"margin"}), "computed": 0})


def test_report_detects_unresolved_claims():
    r = Report(
        run_id="r1",
        format="pdf",
        sections=[ReportSection(key="margins", text="Min margin {c1}", claim_ids=["c1", "c2"])],
        claims=[NumericClaim(id="c1", value=1.5, run_store_ref="runs/r1/margins/0")],
    )
    assert r.unresolved_claim_ids() == {"c2"}


def test_every_schema_exports(tmp_path):
    assert set(ARTIFACT_MODELS) == {
        "geometry",
        "design_graph",
        "cad_script",
        "margins",
        "solver_runs",
        "report",
    }
    paths = write_schemas(tmp_path)
    assert len(paths) == len(all_schemas())
    for p in paths:
        assert json.loads(p.read_text(encoding="utf-8"))["type"] == "object"

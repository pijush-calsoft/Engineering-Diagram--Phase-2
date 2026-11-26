import random

import pytest

from edp_b1_parser import dxf
from edp_b2_interpretation import interpret
from edp_b4_generation import Generation, NoTemplateError, plan_plate, render_plate
from edp_contracts import BlockRequest
from edp_contracts.artifacts.cad_script import CadScript
from edp_contracts.registry import discover_blocks
from edp_eval.synth.construction import sample_base_plate
from edp_eval.synth.dxf_writer import generate
from edp_eval.synth.profiles import PROFILES
from edp_fabric import FabricStore


def drawing_bytes(family: str, seed: int = 1) -> bytes:
    import io

    part = sample_base_plate(random.Random(seed)) if family == "base_plate" else None
    doc, _ = generate(PROFILES["iso"], family, 0, seed, part=part)  # type: ignore[arg-type]
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode()


def graph_for(family: str):
    geometry, _, _ = dxf.parse(drawing_bytes(family), "f", "c")
    return interpret(geometry)[0]


def test_plate_template_traces_every_parameter_to_the_drawing():
    graph = graph_for("base_plate")
    plan = plan_plate(graph)
    names = [p.name for p in plan.params]
    assert names[:3] == ["length", "width", "thickness"]
    assert all(p.source.handle for p in plan.params)  # Phase 4 exit: 100 % parameters with locators
    code = render_plate(plan, "test")
    for p in plan.params:
        assert f"{p.name} = {p.value!r}" in code


def test_bracket_has_no_template_yet():
    with pytest.raises(NoTemplateError, match="bend"):
        plan_plate(graph_for("bracket"))


def test_block_writes_a_cad_script_and_skips_without_a_domain_pack(tmp_path):
    fabric = FabricStore(tmp_path / "fabric")
    up = fabric.ingest("bp.dxf", drawing_bytes("base_plate"), uploader="t")
    geometry, _, _ = dxf.parse(fabric.read(up.uri), up.file_id, up.commit)
    graph = interpret(geometry)[0]
    from edp_contracts import Artifact

    uri = fabric.write("r", "b2_interpretation", "dg.json", graph.model_dump_json().encode())
    art = Artifact(kind="design_graph", uri=uri, schema_version="0.1.0", sources=up.as_artifact().sources)
    block = Generation(fabric)
    skipped = block.run(BlockRequest(run_id="r", inputs=[art]))
    assert skipped.status == "ok" and skipped.outputs[0].uri.startswith("skipped://")
    result = block.run(BlockRequest(run_id="r", inputs=[art], params={"domain_pack": "construction"}))
    assert result.status == "ok" and result.metrics[uri]["template_only"]
    script = CadScript.model_validate_json(fabric.read(result.outputs[0].uri))
    assert script.language == "cadquery" and len(script.parameters) >= 3 + 3 * 4


def test_generation_is_registered():
    assert isinstance(discover_blocks()["b4_generation"], Generation)

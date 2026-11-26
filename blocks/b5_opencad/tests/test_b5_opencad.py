from edp_b5_opencad import OpenCadAdapters, probes_for
from edp_contracts import Artifact, BlockRequest, SourceLocator
from edp_contracts.artifacts.cad_script import CadScript, ScriptParameter
from edp_fabric import FabricStore

LOC = SourceLocator(file_id="f", version="v", handle="1A", confidence=1.0)
PACK = {"domain_pack": "construction"}


def plate_script(hole_d: float = 22.0, model_hole_d: float | None = None) -> CadScript:
    params = {
        "length": 300.0,
        "width": 250.0,
        "thickness": 20.0,
        "hole1_x": 60.0,
        "hole1_y": 60.0,
        "hole1_diameter": hole_d,
    }
    drawn = model_hole_d if model_hole_d is not None else hole_d
    code = (
        "import cadquery as cq\n"
        "result = cq.Workplane('XY').box(300.0, 250.0, 20.0, centered=False)\n"
        f"result = result.cut(cq.Workplane('XY').center(60.0, 60.0).circle({drawn} / 2)"
        ".extrude(22).translate((0, 0, -1)))\n"
    )
    return CadScript(
        language="cadquery",
        code=code,
        parameters=[ScriptParameter(name=k, value=v, unit="mm", source=LOC) for k, v in params.items()],
    )


def run(tmp_path, script: CadScript):
    fabric = FabricStore(tmp_path / "fabric")
    uri = fabric.write("r", "b4_generation", "s.json", script.model_dump_json().encode())
    art = Artifact(kind="cad_script", uri=uri, schema_version="0.1.0", sources=[LOC])
    return OpenCadAdapters(fabric).run(BlockRequest(run_id="r", inputs=[art], params=PACK)), uri, fabric


def test_probes_step_toward_the_plate_centre():
    probes = probes_for(
        {
            "length": 300.0,
            "width": 250.0,
            "thickness": 20.0,
            "hole1_x": 60.0,
            "hole1_y": 60.0,
            "hole1_diameter": 22.0,
        }
    )
    assert [p["expect_inside"] for p in probes] == [False, False, True]
    (rx, ry, _), (wx, wy, wz) = probes[1]["point"], probes[2]["point"]
    assert 60 < rx < wx and 60 < ry < wy and wz == 10.0


def test_valid_model_passes_and_exports_step(tmp_path):
    result, uri, fabric = run(tmp_path, plate_script())
    assert result.status == "ok", result.flags
    m = result.metrics[uri]
    assert m["valid_solid"] and m["features_within_tolerance"] == 1.0
    assert fabric.read(result.outputs[0].uri).startswith(b"ISO-10303-21")


def test_model_that_misses_the_drawing_is_flagged(tmp_path):
    result, uri, _ = run(tmp_path, plate_script(hole_d=22.0, model_hole_d=10.0))
    assert result.status == "needs_review"
    assert any(f.code == "DIMENSION_MISMATCH" for f in result.flags)


def test_broken_script_fails_with_its_error(tmp_path):
    bad = plate_script().model_copy(update={"code": "import cadquery as cq\nresult = 1 / 0\n"})
    result, _, _ = run(tmp_path, bad)
    assert result.status == "failed" and result.flags[0].code == "SCRIPT_ERROR"
    assert "ZeroDivisionError" in result.flags[0].message

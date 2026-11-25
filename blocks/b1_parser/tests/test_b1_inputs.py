"""DWG, vector PDF, STEP, IGES and STL inputs (rest of plan Phase 2)."""

import io
import random
import zlib

import ezdxf
import pytest

from edp_b1_parser import DrawingParser, dwg, dxf, model3d, pdf
from edp_b1_parser.dxf_raw import entity_handles
from edp_contracts import BlockRequest
from edp_eval.synth import write_set
from edp_eval.synth.dwg import dxf2dwg_path, write_dwg_set
from edp_eval.synth.labels import SyntheticLabel
from edp_eval.synth.models import ModelLabel, _build, write_model_set
from edp_eval.synth.parts import Hole, Plate
from edp_eval.synth.pdf import write_pdf
from edp_fabric import FabricStore

HAS_LIBREDWG = dwg.converter() is not None and dwg.converter().is_file()  # type: ignore[union-attr]


@pytest.fixture(scope="module")
def drawings(tmp_path_factory):
    out = tmp_path_factory.mktemp("dxf")
    write_set(out, 2, seed=12, uri_prefix="s3://edp-fabric/golden")
    return out


def labels(folder):
    return [SyntheticLabel.model_validate_json(p.read_text()) for p in sorted(folder.glob("*.labels.json"))]


def doc_bytes(doc) -> bytes:
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode()


# --- DXF robustness used by the DWG path ---------------------------------------------------


def test_dimension_without_geometry_block_is_read_from_its_tags():
    doc = ezdxf.new("R2010", setup=True)
    dim = doc.modelspace().add_linear_dim(
        base=(0, -10), p1=(0, 0), p2=(80, 0), dimstyle="EZDXF", override={"dimlfac": 1}
    )
    dim.render()
    handle, block = dim.dimension.dxf.handle, dim.dimension.dxf.geometry
    doc.blocks.delete_block(block, safe=False)  # what LibreDWG 0.11 output amounts to
    g, flags, _ = dxf.parse(doc_bytes(doc), "f", "c")
    [d] = [e for e in g.entities if e.kind == "dimension"]
    assert d.locator.handle == handle and d.data["value"] == pytest.approx(80.0) and d.data["recovered"]
    assert d.data["p1"] == [0.0, 0.0] and d.data["p2"] == [80.0, 0.0]
    assert any("read from their own tags" in f.message for f in flags)
    assert handle in entity_handles(doc_bytes(doc))


def test_malformed_xdata_is_stripped_not_fatal():
    doc = ezdxf.new("R2010")
    line = doc.modelspace().add_line((0, 0), (10, 0))
    text = doc_bytes(doc).decode()
    marker = f"  5\n{line.dxf.handle}\n"
    broken = text.replace(marker, marker + "1001\nACAD\n1002\n}\n", 1)  # closing marker without opening
    g, flags, _ = dxf.parse(broken.encode(), "f", "c")
    assert [e.kind for e in g.entities] == ["line"]
    assert any("XDATA" in f.message for f in flags)


# --- DWG ----------------------------------------------------------------------------------


def test_missing_converter_fails_the_drawing_not_the_run(tmp_path, monkeypatch, drawings):
    monkeypatch.setenv("EDP_DWG2DXF", str(tmp_path / "no-such-dwg2dxf.exe"))
    fabric = FabricStore(tmp_path / "f")
    up = fabric.ingest("x.dwg", b"AC1032" + b"\0" * 200, uploader="t")
    assert up.kind == "dwg"
    result = DrawingParser(fabric).run(BlockRequest(run_id="r", inputs=[up.as_artifact()]))
    assert result.status == "failed" and result.flags[0].code == "DWG_CONVERSION_FAILED"


@pytest.mark.skipif(not HAS_LIBREDWG, reason="LibreDWG not installed (see docs/setup/local-environment.md)")
def test_dwg_round_trip_keeps_handles_and_values(tmp_path, drawings):
    write_dwg_set(drawings, tmp_path, dxf2dwg_path(dwg.converter()))  # type: ignore[arg-type]
    for lb in labels(tmp_path):
        fabric = FabricStore(tmp_path / "fabric")
        up = fabric.ingest(f"{lb.id}.dwg", (tmp_path / f"{lb.id}.dwg").read_bytes(), uploader="t")
        result = DrawingParser(fabric).run(BlockRequest(run_id=lb.id, inputs=[up.as_artifact()]))
        assert result.status == "ok"
        from edp_contracts.artifacts.geometry import Geometry

        g = Geometry.model_validate_json(fabric.read(result.outputs[0].uri))
        got = {e.locator.handle: e.data["value"] for e in g.entities if e.kind == "dimension"}
        assert got == {d.handle: pytest.approx(d.value) for d in lb.dimensions}
        assert all(loc.file_id == up.file_id for loc in (e.locator for e in g.entities))


@pytest.mark.skipif(not HAS_LIBREDWG, reason="LibreDWG not installed")
def test_unreadable_dwg_is_a_blocking_failure(tmp_path):
    fabric = FabricStore(tmp_path)
    up = fabric.ingest("bad.dwg", b"AC1032" + bytes(random.Random(1).randbytes(500)), uploader="t")
    result = DrawingParser(fabric).run(BlockRequest(run_id="r", inputs=[up.as_artifact()]))
    assert result.status == "failed" and result.flags[0].severity == "block"


# --- Vector PDF ---------------------------------------------------------------------------


def test_vector_pdf_values_title_block_and_units(tmp_path, drawings):
    for lb in labels(drawings):
        write_pdf(drawings / f"{lb.id}.dxf", lb.units, tmp_path / f"{lb.id}.pdf")
        g, flags, m = pdf.parse((tmp_path / f"{lb.id}.pdf").read_bytes(), "f", "c")
        assert flags == [] and g.units == lb.units and m["pages"] == 1
        assert sorted(e.data["value"] for e in g.entities if e.kind == "dimension") == pytest.approx(
            sorted(d.value for d in lb.dimensions)
        )
        assert {k: getattr(g.title_block, k).value for k in lb.title_block} == {
            k: v.value for k, v in lb.title_block.items()
        }
        holes = [f for f in lb.features if f.type == "hole"]
        circles = [e for e in g.entities if e.kind == "circle"]
        # Coordinates in the PDF are written to 0.001 pt (about 0.00035 mm), so fitted circles
        # are compared at that precision; dimension values (text) above are exact.
        assert sorted(2 * c.data["radius"] for c in circles) == pytest.approx(
            sorted(h.parameters["diameter"] for h in holes), abs=1e-3
        )
        assert all(e.locator.handle and e.locator.bbox for e in g.entities)


def _pdf(content: bytes, resources: bytes = b"") -> bytes:
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Resources << "
        + resources
        + b" >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
    ]
    return _assemble(objs)


def _assemble(objs: list[bytes]) -> bytes:
    out = bytearray(b"%PDF-1.4\n")
    offs = []
    for i, body in enumerate(objs, start=1):
        offs.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + b"".join(
        f"{o:010d} 00000 n \n".encode() for o in offs
    )
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n".encode()
    return bytes(out)


def test_pdf_without_units_keeps_points_and_flags():
    g, flags, _ = pdf.parse(_pdf(b"0 0 m 72 0 l S"), "f", "c")
    assert g.units is None and [e.data["end"] for e in g.entities if e.kind == "line"] == [[72.0, 0.0]]
    assert any("[UNITS_UNKNOWN]" in f.message for f in flags)


def test_image_only_pdf_is_reported_as_a_scan():
    image = zlib.compress(b"\x80" * 4)
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Resources << /XObject << /Im1 5 0 R >> >> "
        b"/Contents 4 0 R >>",
        b"<< /Length 31 >>\nstream\nq 100 0 0 100 0 0 cm /Im1 Do Q\nendstream",
        b"<< /Type /XObject /Subtype /Image /Width 2 /Height 2 /ColorSpace /DeviceGray /BitsPerComponent 8 "
        b"/Filter /FlateDecode /Length "
        + str(len(image)).encode()
        + b" >>\nstream\n"
        + image
        + b"\nendstream",
    ]
    _, flags, m = pdf.parse(_assemble(objs), "f", "c")
    assert m["images"] == 1 and "SCANNED_PDF" in {f.code for f in flags}


def test_title_block_scale():
    assert (
        pdf._scale_factor("1:2") == 2.0 and pdf._scale_factor("2:1") == 0.5 and pdf._scale_factor(None) == 1.0
    )


# --- STEP, IGES, STL ----------------------------------------------------------------------


@pytest.fixture(scope="module")
def models(tmp_path_factory):
    out = tmp_path_factory.mktemp("models")
    write_model_set(out, 2, seed=3, uri_prefix="s3://edp-fabric/golden/models")
    return out


def test_step_and_stl_match_the_model(models):
    for p in sorted(models.glob("*.model.json")):
        lb = ModelLabel.model_validate_json(p.read_text())
        g, flags, _ = model3d.parse_brep((models / f"{lb.id}.step").read_bytes(), "step", "f", "c")
        s = g.solids[0]
        assert flags == [] and g.units == "mm"
        assert s.bbox == pytest.approx(lb.bbox, abs=1e-6) and s.volume == pytest.approx(lb.volume, rel=1e-9)
        assert sorted(
            (round(h.diameter, 6), round(h.axis_origin[0], 6), round(h.axis_origin[1], 6)) for h in s.holes
        ) == sorted((round(h.diameter, 6), round(h.x, 6), round(h.y, 6)) for h in lb.holes)
        assert all(loc.handle and loc.handle.startswith("#") for h in s.holes for loc in h.locators)
        mesh = model3d.parse_stl((models / f"{lb.id}.stl").read_bytes(), "f", "c")
        m = mesh[0].solids[0]
        assert m.lossy and m.watertight and m.through_holes_hint == lb.through_openings
        assert {f.code for f in mesh[1]} == {"LOSSY_INPUT", "UNIT_MISMATCH"}


def test_slot_ends_are_not_holes(tmp_path):
    from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer

    part = Plate(
        120.0, 70.0, 6.0, (Hole(10.0, 10.0, 6.6), Hole(110.0, 10.0, 6.6)), slot_length=30.0, slot_width=8.0
    )
    shape, holes, openings = _build(part)
    w = STEPControl_Writer()
    w.Transfer(shape, STEPControl_AsIs)
    w.Write(str(tmp_path / "slot.step"))
    s = model3d.parse_brep((tmp_path / "slot.step").read_bytes(), "step", "f", "c")[0].solids[0]
    assert len(s.holes) == 2 and openings == 3  # the slot's two half-cylinder ends are not holes


def test_iges_reads_holes_with_directory_entry_locators(tmp_path, models):
    from OCP.IGESControl import IGESControl_Writer
    from OCP.STEPControl import STEPControl_Reader

    step = next(models.glob("*.step"))
    r = STEPControl_Reader()
    r.ReadFile(str(step))
    r.TransferRoots()
    w = IGESControl_Writer("MM", 1)
    w.AddShape(r.OneShape())
    w.ComputeModel()
    w.Write(str(tmp_path / "part.igs"))
    g, _, _ = model3d.parse_brep((tmp_path / "part.igs").read_bytes(), "iges", "f", "c")
    lb = ModelLabel.model_validate_json(step.with_suffix("").with_suffix(".model.json").read_text())
    assert len(g.solids[0].holes) == len(lb.holes)
    assert all(loc.handle and loc.handle.startswith("DE") for h in g.solids[0].holes for loc in h.locators)


def test_block_accepts_every_r1_format_and_flags_stl(tmp_path, models):
    parser = DrawingParser(FabricStore(tmp_path))
    assert parser.accepts == {"dxf", "dwg", "pdf", "step", "iges", "stl"}
    fabric = FabricStore(tmp_path)
    stl = next(models.glob("*.stl"))
    up = fabric.ingest(stl.name, stl.read_bytes(), uploader="t")
    result = DrawingParser(fabric).run(BlockRequest(run_id="r", inputs=[up.as_artifact()]))
    assert up.kind == "stl" and result.status == "needs_review"

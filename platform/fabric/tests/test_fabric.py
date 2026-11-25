import io

import pytest
from fastapi.testclient import TestClient

from edp_contracts.events import FABRIC_DATASET_PROMOTED, FABRIC_DATASET_VERSIONED, FABRIC_FILE_INGESTED
from edp_eval.synth.dxf_writer import generate
from edp_eval.synth.profiles import PROFILES
from edp_fabric import FabricStore, UnsupportedTypeError, detect
from edp_fabric.api import create_app
from edp_kit import InMemoryEventBus


def dxf_bytes() -> bytes:
    doc, _ = generate(PROFILES["iso"], "plate", 0, seed=1)
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")


@pytest.mark.parametrize(
    ("data", "kind"),
    [
        (b"%PDF-1.7\n...", "pdf"),
        (b"\x89PNG\r\n\x1a\n....", "image"),
        (b"\xff\xd8\xff\xe0....", "image"),
        (b"AC1032.....", "dwg"),
        (b"ISO-10303-21;\nHEADER;", "step"),
        (b"solid part\n facet normal 0 0 1\n", "stl"),
        (b"\x00" * 80 + (1).to_bytes(4, "little") + b"\x00" * 50, "stl"),
        (b"  0\nSECTION\n  2\nHEADER\n", "dxf"),
    ],
)
def test_detects_type_from_content(data, kind):
    assert detect(data, "anything.bin").kind == kind


def test_detects_real_dxf_and_warns_on_extension_mismatch():
    assert detect(dxf_bytes(), "part.dxf").kind == "dxf"
    d = detect(b"%PDF-1.4", "drawing.dxf")
    assert d.kind == "pdf" and "content is pdf" in (d.warning or "")


def test_unsupported_type_is_an_error_never_a_guess():
    with pytest.raises(UnsupportedTypeError) as e:
        detect(b"hello world", "notes.dxf")
    assert e.value.code == "unsupported_type"


def test_ingest_versions_and_publishes(tmp_path):
    bus = InMemoryEventBus()
    store = FabricStore(tmp_path, bus)
    data = dxf_bytes()
    r = store.ingest("SB 1.dxf", data, uploader="tester")
    assert r.kind == "dxf" and r.uri.startswith("fabric://raw/") and store.read(r.uri) == data
    assert bus.subjects() == [FABRIC_FILE_INGESTED, FABRIC_DATASET_VERSIONED]
    assert bus.history[0].payload == {
        "file_id": r.file_id,
        "type": "dxf",
        "hash": r.file_id,
        "uploader": "tester",
    }
    loc = r.as_artifact().sources[0]
    assert (loc.file_id, loc.version) == (r.file_id, r.commit)
    assert store.ingest("SB 1.dxf", data, uploader="tester").commit == r.commit  # same content, same commit


def test_promotion_goes_one_zone_forward(tmp_path):
    bus = InMemoryEventBus()
    store = FabricStore(tmp_path, bus)
    r = store.ingest("a.dxf", dxf_bytes(), uploader="u")
    cleaned = store.promote(r.dataset_id, "raw", "cleaned")
    final = store.promote(r.dataset_id, "cleaned", "final")
    assert cleaned.parent == r.commit and final.parent == cleaned.commit
    assert store.latest("final", r.dataset_id).commit == final.commit
    assert FABRIC_DATASET_PROMOTED in bus.subjects()
    with pytest.raises(ValueError):
        store.promote(r.dataset_id, "raw", "final")


def test_resolve_refuses_paths_outside_the_root(tmp_path):
    store = FabricStore(tmp_path)
    with pytest.raises(ValueError):
        store.resolve("fabric://raw/ds/c/../../../../etc/passwd")
    with pytest.raises(ValueError):
        store.resolve("s3://bucket/key")


def test_upload_api(tmp_path):
    client = TestClient(create_app(FabricStore(tmp_path)))
    ok = client.post("/files", params={"uploader": "u"}, files={"file": ("p.dxf", dxf_bytes())})
    assert ok.status_code == 200 and ok.json()["kind"] == "dxf"
    bad = client.post("/files", params={"uploader": "u"}, files={"file": ("x.dxf", b"not a drawing")})
    assert bad.status_code == 415 and bad.json()["detail"]["code"] == "unsupported_type"
    promoted = client.post(
        f"/datasets/{ok.json()['dataset_id']}/promote", params={"from_zone": "raw", "to_zone": "cleaned"}
    )
    assert promoted.status_code == 200

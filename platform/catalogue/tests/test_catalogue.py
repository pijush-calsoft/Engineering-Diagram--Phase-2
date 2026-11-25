import pytest
from fastapi.testclient import TestClient

from edp_catalogue import Catalogue, create_app
from edp_contracts import Artifact, SourceLocator
from edp_contracts.events import CATALOGUE_LINEAGE_RECORDED
from edp_kit import InMemoryEventBus


def art(*handles: str, file_id: str = "f1") -> Artifact:
    locs = [SourceLocator(file_id=file_id, version="c1", handle=h, confidence=0.9) for h in handles]
    return Artifact(
        kind="geometry", uri="fabric://cleaned/ds/c1/geometry.json", schema_version="0.1.0", sources=locs
    )


def test_register_keeps_every_locator_in_order(tmp_path):
    bus = InMemoryEventBus()
    cat = Catalogue(tmp_path / "cat.sqlite", bus)
    aid = cat.register("r1", "b1_parser", "0.1", art("8A", "8F", "AE"))
    assert [s.handle for s in cat.lineage(aid)] == ["8A", "8F", "AE"]
    rec = cat.get(aid)
    assert rec.block == "b1_parser" and rec.artifact.kind == "geometry"
    assert bus.subjects() == [CATALOGUE_LINEAGE_RECORDED]
    assert bus.history[0].payload["output_item"] == aid


def test_trace_back_from_a_file(tmp_path):
    cat = Catalogue(tmp_path / "cat.sqlite")
    a = cat.register("r1", "b1_parser", "0.1", art("1"))
    b = cat.register("r1", "b2_interpretation", "0.1", art("2"))
    cat.register("r2", "b1_parser", "0.1", art("3", file_id="other"))
    assert [r.id for r in cat.derived_from("f1")] == [a, b]
    assert len(cat.by_run("r1")) == 2


def test_catalogue_persists_across_connections(tmp_path):
    path = tmp_path / "cat.sqlite"
    aid = Catalogue(path).register("r1", "b1_parser", "0.1", art("1"))
    assert Catalogue(path).lineage(aid)[0].handle == "1"


def test_api(tmp_path):
    cat = Catalogue(tmp_path / "cat.sqlite")
    aid = cat.register("r1", "b1_parser", "0.1", art("1"))
    client = TestClient(create_app(cat))
    assert client.get(f"/artifacts/{aid}/lineage").json()[0]["handle"] == "1"
    assert client.get("/artifacts/nope/lineage").status_code == 404
    assert len(client.get("/runs/r1/artifacts").json()) == 1
    with pytest.raises(KeyError):
        cat.get("nope")

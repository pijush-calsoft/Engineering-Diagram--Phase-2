import pytest
from fastapi.testclient import TestClient

from edp_contracts import Artifact, BlockRequest, BlockResult, SourceLocator
from edp_contracts.events import RUN_BLOCK_COMPLETED, RUN_BLOCK_FAILED, RUN_BLOCK_STARTED
from edp_kit import InMemoryEventBus, UnknownSubjectError, create_block_app, run_block


class Echo:
    name = "echo"
    version = "1.0"
    accepts = {"geometry"}
    produces = {"geometry"}

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def run(self, req: BlockRequest) -> BlockResult:
        if self.fail:
            raise RuntimeError("boom")
        return BlockResult(run_id=req.run_id, status="ok", outputs=req.inputs, metrics={"n": len(req.inputs)})


def request(kind: str = "geometry") -> BlockRequest:
    loc = SourceLocator(file_id="f", version="c", confidence=1)
    return BlockRequest(
        run_id="r1", inputs=[Artifact(kind=kind, uri="fabric://x", schema_version="0.1.0", sources=[loc])]
    )


def test_bus_rejects_unknown_subjects_and_filters_by_prefix():
    bus = InMemoryEventBus()
    seen = []
    bus.subscribe("run.", seen.append)
    with pytest.raises(UnknownSubjectError):
        bus.publish("run.whatever", {})
    bus.publish("fabric.file.ingested", {})
    bus.publish(RUN_BLOCK_STARTED, {"run_id": "r"})
    assert [e.subject for e in seen] == [RUN_BLOCK_STARTED]
    assert [e.seq for e in bus.history] == [1, 2]


def test_run_block_publishes_started_and_completed_with_appendix_b_fields():
    bus = InMemoryEventBus()
    run_block(Echo(), request(), bus)
    assert bus.subjects() == [RUN_BLOCK_STARTED, RUN_BLOCK_COMPLETED]
    done = bus.history[-1].payload
    assert {"run_id", "block", "version", "metrics", "flags"} <= done.keys()


def test_run_block_publishes_failed_and_reraises():
    bus = InMemoryEventBus()
    with pytest.raises(RuntimeError):
        run_block(Echo(fail=True), request(), bus)
    assert bus.subjects() == [RUN_BLOCK_STARTED, RUN_BLOCK_FAILED]


def test_run_block_rejects_kinds_the_block_does_not_accept():
    with pytest.raises(ValueError):
        run_block(Echo(), request("margins"))


def test_http_endpoints():
    client = TestClient(create_block_app(Echo(), schema_versions={"geometry": "0.1.0"}))
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/contract").json()["accepts"] == ["geometry"]
    r = client.post("/run", json=request().model_dump(mode="json"))
    assert r.status_code == 200 and BlockResult.model_validate(r.json()).status == "ok"
    assert client.post("/run", json=request("margins").model_dump(mode="json")).status_code == 422
    failing = TestClient(create_block_app(Echo(fail=True)))
    assert failing.post("/run", json=request().model_dump(mode="json")).status_code == 500


def test_overrides_accept_only_known_positive_sizes():
    from edp_kit import OverrideError, overrides, parse_overrides

    assert parse_overrides(None) == {} and parse_overrides({"thickness": 25}) == {"thickness": 25.0}
    req = BlockRequest(run_id="r", inputs=[], params={"overrides": {"thickness": 12.5}})
    assert overrides(req) == {"thickness": 12.5}
    for bad in ({"length": 300}, {"thickness": 0}, {"thickness": "25"}, {"thickness": True}, [25]):
        with pytest.raises(OverrideError):
            parse_overrides(bad)

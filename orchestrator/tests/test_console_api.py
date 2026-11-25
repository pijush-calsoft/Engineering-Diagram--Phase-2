import time

import pytest
from fastapi.testclient import TestClient

from edp_eval.synth import write_set
from edp_orchestrator.server import Console, create_app


@pytest.fixture()
def client(tmp_path):
    golden = tmp_path / "golden"
    write_set(golden, 2, seed=6, uri_prefix="s3://edp-fabric/golden")
    console = Console(tmp_path / "data", golden)
    return TestClient(create_app(console)), console


def wait(client: TestClient, run_id: str) -> dict:
    for _ in range(200):
        view = client.get(f"/api/runs/{run_id}").json()
        if not view["running"]:
            return view
        time.sleep(0.05)
    raise AssertionError("run did not finish")


def test_blocks_list_real_and_stub(client):
    c, _ = client
    blocks = {b["name"]: b["real"] for b in c.get("/api/blocks").json()}
    assert (
        len(blocks) == 8 and blocks["b1_parser"] and blocks["b2_interpretation"] and not blocks["b8_report"]
    )


def test_sample_run_end_to_end(client):
    c, _ = client
    name = c.get("/api/samples").json()[0]
    started = c.post("/api/runs/sample", params={"name": name}).json()
    view = wait(c, started["run_id"])
    assert view["status"]["state"] == "completed" and len(view["status"]["results"]) == 8
    kinds = {a["kind"]: a["uri"] for a in view["artifacts"]}
    geometry = c.get("/api/artifact", params={"uri": kinds["geometry"]}).json()
    graph = c.get("/api/artifact", params={"uri": kinds["design_graph"]}).json()
    assert geometry["entities"] and any(n["kind"] == "feature" for n in graph["nodes"])
    events = c.get(f"/api/runs/{started['run_id']}/events").text
    assert "event: run.planned" in events and events.count("event: run.block.completed") == 8
    assert events.rstrip().endswith("data: {}")


def test_upload_review_and_errors(client, tmp_path):
    c, console = client
    bad = c.post("/api/runs", files={"file": ("x.dxf", b"not a drawing")})
    assert bad.status_code == 415
    path = next((tmp_path / "golden").glob("*.dxf"))
    console.blocks[2].status = "needs_review"  # stub b3 asks for review
    started = c.post("/api/runs", files={"file": (path.name, path.read_bytes())}).json()
    assert wait(c, started["run_id"])["status"]["state"] == "awaiting_review"
    assert (
        c.post(
            f"/api/runs/{started['run_id']}/review", json={"decision": "approve", "reviewer": "lead"}
        ).status_code
        == 200
    )
    assert wait(c, started["run_id"])["status"]["state"] == "completed"
    assert (
        c.post(
            f"/api/runs/{started['run_id']}/review", json={"decision": "approve", "reviewer": "lead"}
        ).status_code
        == 409
    )
    assert c.get("/api/runs/run-nope").status_code == 404
    assert c.get("/api/artifact", params={"uri": "fabric://raw/x/y/z"}).status_code == 400
    assert c.post("/api/runs/sample", params={"name": "../secret.dxf"}).status_code == 404

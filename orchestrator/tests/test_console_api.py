import json
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from edp_eval.synth import write_set
from edp_gateway import Gateway, GatewayConfig
from edp_gateway.backend import Reply
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
    assert len(blocks) == 8 and blocks["b1_parser"] and blocks["b2_interpretation"] and blocks["b8_report"]
    assert not blocks["b7_surrogate"]  # the only stub left (surrogate and envelope not built)


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
    # Stub b7 asks for review. Blocks 4 to 6 and 8 are real but pass a run with no domain pack through.
    console.blocks[6].status = "needs_review"
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


class FakeModel:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    def complete(self, model: str, messages: list[dict[str, Any]], **options: Any) -> Reply:
        self.messages = messages
        reply = {"answer": "It is in the title block.", "citations": ["TB.material"], "from_facts": True}
        return Reply(json.dumps(reply), model, 50, 10, 0.0005, "test")

    def embed(self, model: str, texts: list[str], **options: Any) -> Any:
        raise NotImplementedError


def gateway(tmp_path, key: str = "k") -> tuple[Gateway, FakeModel]:
    fake = FakeModel()
    cfg = GatewayConfig(
        api_key=key, provider="openai", models={"text": "m"}, embedding_model=None, budget_usd=None,
        redact_terms=(), timeout_s=None, max_retries=None, data_dir=tmp_path / "gw",
    )
    return Gateway(cfg, backend=fake), fake


def test_chat_answers_with_citations_from_the_run(tmp_path):
    gw, fake = gateway(tmp_path)
    golden = tmp_path / "golden"
    write_set(golden, 1, seed=6, uri_prefix="s3://edp-fabric/golden")
    c = TestClient(create_app(Console(tmp_path / "data", golden, gateway=gw)))
    assert c.get("/api/chat").json() == {"available": True, "reason": None, "model": "m"}
    run_id = c.post("/api/runs/sample", params={"name": c.get("/api/samples").json()[0]}).json()["run_id"]
    wait(c, run_id)
    ans = c.post(f"/api/runs/{run_id}/chat", json={"question": "What material?", "history": []}).json()
    assert ans["from_facts"] and ans["citations"][0]["id"] == "TB.material"
    assert ans["citations"][0]["handles"]  # the citation points back into the drawing
    assert "[TB.material]" in fake.messages[1]["content"][0]["text"]
    row = gw.usage.calls()[0]
    assert row["data_class"] == "synthetic" and row["run_id"] == run_id
    assert c.get("/api/usage").json() == {"spent_usd": 0.0005, "calls": 1}
    assert c.post(f"/api/runs/{run_id}/chat", json={"question": " "}).status_code == 400
    assert c.post("/api/runs/run-nope/chat", json={"question": "q"}).status_code == 404


def test_chat_is_unavailable_without_a_key(tmp_path):
    gw, _ = gateway(tmp_path, key="")
    c = TestClient(create_app(Console(tmp_path / "data", None, gateway=gw)))
    status = c.get("/api/chat").json()
    assert not status["available"] and "OPENAI_API_KEY" in status["reason"]


def test_runs_list_source_image_and_mesh(tmp_path):
    import cv2
    import numpy as np

    from edp_eval.synth.models import write_model_set

    models = tmp_path / "models"
    write_model_set(models, 1, 3, "s3://edp-fabric/golden/models")
    gw, _ = gateway(tmp_path)
    console = Console(tmp_path / "data", [models], gateway=gw)
    c = TestClient(create_app(console))
    step = next(n for n in c.get("/api/samples").json() if n.endswith(".step"))
    run_id = c.post("/api/runs/sample", params={"name": step}).json()["run_id"]
    wait(c, run_id)
    (summary,) = c.get("/api/runs").json()
    assert summary["run_id"] == run_id and summary["kind"] == "step" and summary["data_class"] == "synthetic"
    mesh = c.get(f"/api/runs/{run_id}/mesh").json()
    assert len(mesh["indices"]) % 3 == 0 and mesh["faces"] and mesh["faces"][0]["handle"].startswith("#")
    assert c.get(f"/api/runs/{run_id}/source").status_code == 415
    png = cv2.imencode(".png", np.full((20, 30), 255, np.uint8))[1].tobytes()
    upload = console.start("scan.png", png)  # client data: the parser refuses to send it
    wait(c, upload.run_id)
    img = c.get(f"/api/runs/{upload.run_id}/source")
    assert img.status_code == 200 and img.headers["content-type"] == "image/png" and img.content == png
    assert c.get(f"/api/runs/{upload.run_id}/mesh").status_code == 415
    assert c.get("/api/runs/run-nope/mesh").status_code == 404

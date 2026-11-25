"""Cited answers with a fake model backend: no network, no key, no cost."""

import json
from pathlib import Path
from typing import Any

from edp_catalogue.answer import Turn, cited_answer, facts_from_run
from edp_gateway import Gateway, GatewayConfig
from edp_gateway.backend import EmbeddingReply, Reply


def loc(handle: str) -> dict[str, Any]:
    return {"file_id": "f", "version": "v", "handle": handle, "confidence": 1.0}


GEOMETRY = {
    "units": "mm",
    "title_block": {"material": {"value": "S355", "locator": loc("TB1")}, "revision": None},
    "entities": [
        {"kind": "dimension", "locator": loc("D10"), "data": {"dimtype": "linear", "value": 120.0}},
        {
            "kind": "dimension",
            "locator": loc("D11"),
            "data": {"dimtype": "diameter", "value": 6.5, "displayed": "%%c6.5"},
        },
        {"kind": "text", "locator": loc("T20"), "data": {"text": "BREAK ALL EDGES"}},
        {"kind": "line", "locator": loc("L1"), "data": {}},
    ],
    "solids": [],
}
GRAPH = {
    "nodes": [
        {
            "id": "hole1",
            "kind": "feature",
            "feature_type": "hole",
            "attributes": {"count": 1},
            "sources": [loc("C5")],
        },
        {
            "id": "hole1.diameter",
            "kind": "parameter",
            "feature_type": None,
            "attributes": {"value": 6.5, "unit": "mm", "confidence": 0.95},
            "sources": [loc("D11")],
        },
    ]
}
FLAGS = [{"code": "LOW_CONFIDENCE", "severity": "review", "message": "check", "target": loc("D10")}]


class FakeBackend:
    def __init__(self, reply: dict[str, Any]):
        self.reply = reply
        self.messages: list[dict[str, Any]] = []

    def complete(self, model: str, messages: list[dict[str, Any]], **options: Any) -> Reply:
        self.messages = messages
        return Reply(json.dumps(self.reply), model, 100, 20, 0.001, "test")

    def embed(self, model: str, texts: list[str], **options: Any) -> EmbeddingReply:
        raise NotImplementedError


def gateway(tmp_path: Path, reply: dict[str, Any]) -> tuple[Gateway, FakeBackend]:
    fake = FakeBackend(reply)
    cfg = GatewayConfig(
        api_key="k",
        provider="openai",
        models={"text": "m"},
        embedding_model=None,
        budget_usd=None,
        redact_terms=(),
        timeout_s=None,
        max_retries=None,
        data_dir=tmp_path,
    )
    return Gateway(cfg, backend=fake), fake


def test_facts_carry_ids_and_source_handles():
    facts = {f.id: f for f in facts_from_run(GEOMETRY, GRAPH, None, FLAGS)}
    assert facts["UNITS"].text == "drawing units: mm"
    assert facts["TB.material"].handles == ["TB1"] and "S355" in facts["TB.material"].text
    assert facts["D2"].text == "diameter dimension 6.5, shown as '%%c6.5'" and facts["D2"].handles == ["D11"]
    assert facts["T1"].handles == ["T20"]
    assert facts["hole1.diameter"].handles == ["D11"]
    assert facts["hole1.diameter"].text == "diameter 6.5 mm (confidence 0.95)"
    assert facts["hole1"].text == "hole (count 1)"
    assert facts["FL1"].handles == ["D10"]
    assert not any(f.id.startswith("L") for f in facts.values())  # plain geometry is not sent


def test_answer_maps_citations_to_handles(tmp_path):
    gw, fake = gateway(
        tmp_path, {"answer": "The hole is 6.5 mm.", "citations": ["hole1.diameter", "D2"], "from_facts": True}
    )
    facts = facts_from_run(GEOMETRY, GRAPH, None, FLAGS)
    ans = cited_answer(gw, "How big is the hole?", facts, data_class="synthetic", run_id="r1")
    assert ans.from_facts and [c.id for c in ans.citations] == ["hole1.diameter", "D2"]
    assert ans.citations[0].handles == ["D11"]
    assert ans.cost_usd == 0.001 and ans.facts == len(facts)
    system, user = fake.messages
    assert "Use only these facts" in system["content"]
    assert "[hole1.diameter]" in user["content"][0]["text"]  # facts go as data
    assert user["content"][-1]["text"] == "How big is the hole?"  # the question goes as the request
    assert gw.usage.calls()[0]["service"] == "console_chat"


def test_unknown_and_missing_citations_are_flagged(tmp_path):
    gw, _ = gateway(tmp_path, {"answer": "Made up.", "citations": ["X99"], "from_facts": True})
    ans = cited_answer(gw, "q", facts_from_run(GEOMETRY, GRAPH, None, []), data_class="synthetic")
    codes = {f.code for f in ans.flags}
    assert codes >= {"UNKNOWN_CITATION", "UNCITED_ANSWER"}
    assert not ans.from_facts and ans.citations == []


def test_history_is_sent_as_data(tmp_path):
    gw, fake = gateway(tmp_path, {"answer": "No.", "citations": [], "from_facts": False})
    history = [Turn(question=f"q{i}", answer=f"a{i}") for i in range(5)]
    cited_answer(gw, "and now?", [], data_class="client", history=history)
    data = fake.messages[1]["content"][0]["text"]
    assert "q4" in data and "q2" in data and "q1" not in data  # only the last three turns
    assert "(the run has no results yet)" in data

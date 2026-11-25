"""Cited answers about one run (plan Phase 1, Data Catalogue: "cited answer" endpoint).

The run's artifacts are turned into numbered facts, each carrying the source handles it
came from (plan principle 1: no output item without a source locator). The model is asked,
through the Model Gateway, to answer only from those facts and to cite their ids. The reply is
checked here, not trusted:

- a cited id that is not one of the facts is dropped and flagged ``UNKNOWN_CITATION``;
- an answer that claims to come from the facts but cites none is flagged ``UNCITED_ANSWER``.

The facts are drawing content, so they go to the gateway as untrusted ``inputs`` (sent as data,
redacted and screened); the engineer's question goes as the gateway's ``user`` request.
"""

from typing import Any

from pydantic import BaseModel

from edp_contracts import Flag
from edp_gateway import CompletionRequest, DataClass, Gateway

PROMPT_VERSION = "cited-answer-1"
INSTRUCTIONS = """You answer an engineer's questions about one engineering drawing or model that the
platform has read. The facts the platform extracted are given as lines inside <data>; each line
starts with its id in square brackets, for example [D3].

Rules:
- Use only these facts. Do not add values, standards or advice that the facts do not contain.
- Cite the id of every fact you use in "citations".
- If the facts do not answer the question, say so plainly and set "from_facts" to false.
- Keep units exactly as the facts give them. Simple arithmetic on fact values is allowed; show it.
- Answer in a few short sentences."""
MAX_TEXTS = 80  # drawing text entities included as facts; the rest are counted, not sent
HISTORY_TURNS = 3  # earlier question and answer pairs sent with a new question


class Fact(BaseModel):
    id: str
    text: str
    handles: list[str] = []


class Turn(BaseModel):
    question: str
    answer: str


class Citation(BaseModel):
    id: str
    text: str
    handles: list[str]


class CitedAnswer(BaseModel):
    answer: str
    from_facts: bool
    citations: list[Citation]
    flags: list[Flag] = []
    cost_usd: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    facts: int


class _Reply(BaseModel):
    answer: str
    citations: list[str]
    from_facts: bool


def _handles(locators: list[dict[str, Any]] | None) -> list[str]:
    return [loc["handle"] for loc in locators or [] if loc.get("handle")]


def _fmt(value: Any) -> str:
    return f"{value:g}" if isinstance(value, float) else str(value)


_SHOWN = {"name", "value", "unit", "value_mm"}  # parameter attributes that form the main phrase


def _node_text(node: dict[str, Any]) -> str:
    """A design graph node as a readable phrase: "diameter 6.5 mm (by value, confidence 0.95)"."""
    a = node.get("attributes") or {}
    extra = ", ".join(
        f"{k.replace('_', ' ')} {_fmt(v)}"
        for k, v in a.items()
        if k not in _SHOWN and isinstance(v, str | int | float) and not isinstance(v, bool)
    )
    if node["kind"] == "parameter":
        name = a.get("name") or node["id"].rsplit(".", 1)[-1]
        head = f"{name} {_fmt(a.get('value'))} {a.get('unit') or ''}".strip()
    else:
        head = node.get("feature_type") or node["kind"]
    return f"{head} ({extra})" if extra else head


def facts_from_run(
    geometry: dict[str, Any] | None,
    design_graph: dict[str, Any] | None,
    similar_parts: dict[str, Any] | None,
    flags: list[dict[str, Any]],
) -> list[Fact]:
    """Numbered facts from the run's artifacts, each with the handles it came from."""
    facts: list[Fact] = []
    if geometry:
        facts.append(Fact(id="UNITS", text=f"drawing units: {geometry.get('units') or 'not stated'}"))
        for name, field in (geometry.get("title_block") or {}).items():
            if field and field.get("value"):
                handle = (field.get("locator") or {}).get("handle")
                facts.append(
                    Fact(
                        id=f"TB.{name}",
                        text=f"title block {name.replace('_', ' ')}: {field['value']}",
                        handles=[handle] if handle else [],
                    )
                )
        dims = [e for e in geometry.get("entities", []) if e["kind"] == "dimension"]
        for n, e in enumerate(dims, 1):
            d = e["data"]
            shown = f", shown as '{d['displayed']}'" if d.get("displayed") else ""
            facts.append(
                Fact(
                    id=f"D{n}",
                    text=f"{d.get('dimtype', 'dimension')} dimension {_fmt(d.get('value'))}{shown}",
                    handles=_handles([e["locator"]]),
                )
            )
        texts = [e for e in geometry.get("entities", []) if e["kind"] == "text" and e["data"].get("text")]
        for n, e in enumerate(texts[:MAX_TEXTS], 1):
            facts.append(
                Fact(id=f"T{n}", text=f"drawing text: {e['data']['text']}", handles=_handles([e["locator"]]))
            )
        if len(texts) > MAX_TEXTS:
            facts.append(Fact(id="T.more", text=f"{len(texts) - MAX_TEXTS} further text items not listed"))
        for n, s in enumerate(geometry.get("solids") or [], 1):
            b = s["bbox"]
            size = " x ".join(_fmt(round(b[i + 3] - b[i], 6)) for i in range(3))
            facts.append(
                Fact(
                    id=f"S{n}",
                    text=f"3D solid: size {size}, volume {_fmt(s.get('volume'))}, faces {s.get('faces')}, "
                    f"{len(s.get('holes', []))} hole(s)",
                    handles=_handles([s["locator"]]),
                )
            )
            for k, h in enumerate(s.get("holes", []), 1):
                o = h["axis_origin"]
                facts.append(
                    Fact(
                        id=f"S{n}.H{k}",
                        text=f"3D hole: diameter {_fmt(h['diameter'])}, axis through "
                        f"({_fmt(o[0])}, {_fmt(o[1])}, {_fmt(o[2])})",
                        handles=_handles(h.get("locators")),
                    )
                )
    for node in (design_graph or {}).get("nodes", []):
        facts.append(Fact(id=node["id"], text=_node_text(node), handles=_handles(node.get("sources"))))
    if similar_parts:
        for n, sp in enumerate(similar_parts.get("similar", []), 1):
            rev = f" rev {sp['revision']}" if sp.get("revision") else ""
            facts.append(
                Fact(id=f"SP{n}", text=f"similar part {sp['part_number']}{rev}, score {_fmt(sp['score'])}")
            )
        for c in similar_parts.get("corroborations", []):
            agree = sum(1 for e in c.get("evidence", []) if e.get("agrees"))
            facts.append(
                Fact(
                    id=f"KG.{c['parameter']}",
                    text=f"knowledge graph check of {c['parameter']} = {_fmt(c['value'])}: {c['status']}, "
                    f"{agree} of {len(c.get('evidence', []))} similar parts agree",
                )
            )
    for n, f in enumerate(flags, 1):
        target = f.get("target") or {}
        facts.append(
            Fact(
                id=f"FL{n}",
                text=f"flag {f['code']} ({f['severity']}): {f['message']}",
                handles=[target["handle"]] if target.get("handle") else [],
            )
        )
    return facts


def cited_answer(
    gateway: Gateway,
    question: str,
    facts: list[Fact],
    data_class: DataClass,
    run_id: str | None = None,
    history: list[Turn] | None = None,
) -> CitedAnswer:
    lines = "\n".join(f"[{f.id}] {f.text}" for f in facts) or "(the run has no results yet)"
    inputs = [lines]
    for t in (history or [])[-HISTORY_TURNS:]:
        inputs.append(f"Earlier question: {t.question}\nEarlier answer: {t.answer}")
    result = gateway.complete(
        CompletionRequest(
            service="console_chat",
            role="text",
            instructions=INSTRUCTIONS,
            prompt_version=PROMPT_VERSION,
            inputs=inputs,
            user=question,
            data_class=data_class,
            run_id=run_id,
        ),
        output_model=_Reply,
    )
    reply: _Reply = result.parsed
    by_id = {f.id: f for f in facts}
    flags = list(result.flags)
    unknown = [c for c in reply.citations if c not in by_id]
    if unknown:
        flags.append(
            Flag(
                code="UNKNOWN_CITATION", severity="review", message=f"cited ids that are not facts: {unknown}"
            )
        )
    cited = [by_id[c] for c in dict.fromkeys(reply.citations) if c in by_id]
    if reply.from_facts and not cited:
        flags.append(
            Flag(
                code="UNCITED_ANSWER",
                severity="review",
                message="the answer cites no fact; treat it as unsupported",
            )
        )
    return CitedAnswer(
        answer=reply.answer,
        from_facts=reply.from_facts and bool(cited),
        citations=[Citation(id=f.id, text=f.text, handles=f.handles) for f in cited],
        flags=flags,
        cost_usd=result.usage.cost_usd,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        facts=len(facts),
    )

import hashlib
import json

import pytest

from edp_b1_parser import DrawingParser, dxf
from edp_b2_interpretation import Interpretation, interpret
from edp_b3_knowledge_graph import (
    KnowledgeGraph,
    SqliteGraphStore,
    corroborate,
    descriptor,
    ingest,
    revision_id,
    similar_parts,
    similarity,
)
from edp_b3_knowledge_graph.store import (
    FEATURE,
    HAS_FEATURE,
    HAS_REVISION,
    MADE_OF,
    PART,
    REVISION,
    Edge,
    Node,
)
from edp_catalogue import Catalogue
from edp_contracts import Block, SourceLocator
from edp_contracts.registry import discover_blocks
from edp_eval.suites.knowledge_graph import run
from edp_eval.synth import write_family_set
from edp_eval.synth.labels import SyntheticLabel
from edp_fabric import FabricStore
from edp_kit import InMemoryEventBus
from edp_orchestrator import Orchestrator, stub_blocks


@pytest.fixture(scope="module")
def families(tmp_path_factory):
    out = tmp_path_factory.mktemp("families")
    write_family_set(out, families=8, revisions=3, seed=5, uri_prefix="s3://edp-fabric/golden/families")
    return out


def read(path):
    data = path.read_bytes()
    loc = SourceLocator(file_id=hashlib.sha256(data).hexdigest(), version="v1", confidence=1.0)
    geometry, _, _ = dxf.parse(data, loc.file_id, loc.version)
    graph, _, _ = interpret(geometry)
    return geometry, graph, loc


def label(path):
    return SyntheticLabel.model_validate_json(path.with_suffix("").with_suffix(".labels.json").read_text())


def test_store_upserts_are_idempotent():
    s = SqliteGraphStore(":memory:")
    s.upsert_node(Node(id="a", label=PART, props={"v": 1}))
    s.upsert_node(Node(id="a", label=PART, props={"v": 2}))
    s.upsert_node(Node(id="b", label=REVISION))
    s.upsert_edge(Edge(source="a", relation=HAS_REVISION, target="b"))
    s.upsert_edge(Edge(source="a", relation=HAS_REVISION, target="b"))
    assert s.node("a").props == {"v": 2} and [n.id for n in s.out("a", HAS_REVISION)] == ["b"]
    assert s.node("missing") is None


def test_ingest_builds_part_revision_material_features(families):
    path = next(families.glob("fam-iso-plate-000A.dxf"))
    geometry, graph, loc = read(path)
    s = SqliteGraphStore(":memory:")
    rid = ingest(s, graph, geometry.title_block, loc)
    assert rid.startswith("rev:EDP-FAM-000@A@")
    assert [n.id for n in s.out("part:EDP-FAM-000", HAS_REVISION)] == [rid]
    assert s.out(rid, MADE_OF)[0].props["name"] == geometry.title_block.material.value
    feats = s.out(rid, HAS_FEATURE)
    assert feats and all(f.label == FEATURE for f in feats)
    hole = next(f for f in feats if f.props["type"] == "hole")
    assert hole.props["params"]["diameter"]["sources"][0]["file_id"] == loc.file_id
    assert ingest(s, graph, geometry.title_block, loc) == rid and len(s.nodes(REVISION)) == 1


def test_similarity_ranks_revisions_above_other_parts(families):
    _, a, _ = read(families / "fam-iso-plate-000A.dxf")
    _, b, _ = read(families / "fam-iso-plate-000B.dxf")
    _, other, _ = read(families / "fam-iso-bracket-002A.dxf")
    da, db, do = descriptor(a), descriptor(b), descriptor(other)
    assert similarity(da, da) == pytest.approx(1.0)
    assert similarity(da, db) > similarity(da, do)
    assert similarity(da, db) == pytest.approx(similarity(db, da))


def corroborations(families, query_name):
    s = SqliteGraphStore(":memory:")
    for p in sorted(families.glob("*.dxf")):
        if p.name != query_name:
            geometry, graph, loc = read(p)
            ingest(s, graph, geometry.title_block, loc)
    geometry, graph, loc = read(families / query_name)
    rid, part_number, _ = revision_id(geometry.title_block, loc)
    return corroborate(s, graph, similar_parts(s, graph, exclude=rid, top=3), part_number)


def test_omitted_value_is_resolved_by_sibling_revisions(families):
    [c] = corroborations(families, "fam-iso-plate-000C.dxf")  # family 0: not adversarial
    assert c.parameter.endswith(".diameter") and c.status == "resolved"
    assert c.confidence == pytest.approx(0.9)  # two agreeing revisions: 0.7 + 2 x 0.1
    assert sum(e.same_part and e.agrees for e in c.evidence) == 2
    assert all(e.sources for e in c.evidence)


def test_changed_value_is_left_to_a_person(families):
    [c] = corroborations(families, "fam-iso-plate-004C.dxf")  # family 4: adversarial (f // 4 odd)
    assert c.status == "conflict" and c.confidence == pytest.approx(0.7)
    assert any(e.same_part and not e.agrees for e in c.evidence)


def test_no_similar_parts_means_no_evidence(families):
    geometry, graph, loc = read(families / "fam-iso-plate-000C.dxf")
    [c] = corroborate(SqliteGraphStore(":memory:"), graph, [], "EDP-FAM-000")
    assert c.status == "no_evidence" and c.evidence == []


def test_block_in_the_pipeline_with_real_blocks_1_to_3(tmp_path, families, monkeypatch):
    monkeypatch.setenv("EDP_DATA_DIR", str(tmp_path))
    assert isinstance(discover_blocks()["b3_knowledge_graph"], KnowledgeGraph)
    bus = InMemoryEventBus()
    fabric = FabricStore(tmp_path / "fabric", bus)
    catalogue = Catalogue(tmp_path / "c.sqlite", bus)
    blocks: list[Block] = list(stub_blocks())
    blocks[:3] = [
        DrawingParser(fabric),
        Interpretation(fabric),
        KnowledgeGraph(fabric, SqliteGraphStore(tmp_path / "kg.sqlite")),
    ]
    orch = Orchestrator(blocks, catalogue, bus, tmp_path / "cp.sqlite")

    def run_drawing(name: str, run_id: str):
        up = fabric.ingest(name, (families / name).read_bytes(), uploader="t")
        return orch.start(run_id, [up.as_artifact()])

    assert run_drawing("fam-iso-plate-000A.dxf", "r1").state == "completed"
    assert run_drawing("fam-iso-plate-000B.dxf", "r2").state == "completed"
    done = run_drawing("fam-iso-plate-000C.dxf", "r3")  # hole 1 diameter omitted, siblings agree
    assert done.state == "completed"
    assert any(f["code"] == "CORROBORATED" for r in done.results for f in r["flags"])
    art = next(r for r in catalogue.by_run("r3") if r.artifact.kind == "similar_parts")
    body = json.loads(fabric.read(art.artifact.uri))
    assert body["corroborations"][0]["status"] == "resolved" and len(body["similar"]) == 2

    run_drawing("fam-iso-plate-004A.dxf", "r4")
    run_drawing("fam-iso-plate-004B.dxf", "r5")
    paused = run_drawing("fam-iso-plate-004C.dxf", "r6")  # hole 1 changed: siblings disagree
    assert paused.state == "awaiting_review" and paused.next == ["review"]
    assert any("[CONFLICTING_EVIDENCE]" in f["message"] for r in paused.results for f in r["flags"])


def test_suite_meets_targets_and_can_fail(families, tmp_path):
    report = run(families)
    assert report["recall_at_3"] == 1.0 and report["corroboration"]["resolved_wrongly"] == 0
    # Break the groups: recall must drop, so the suite is not a tautology.
    for p in families.glob("*.dxf"):
        (tmp_path / p.name).write_bytes(p.read_bytes())
        lb = label(p)
        (tmp_path / f"{lb.id}.labels.json").write_text(
            lb.model_copy(update={"group": f"solo-{lb.id}"}).model_dump_json()
        )
    assert run(tmp_path)["recall_at_3"] == 0.0

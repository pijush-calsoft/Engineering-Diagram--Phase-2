"""Property-graph store for the Knowledge Graph (plan Phase 3, KG task 1).

The plan's store is Apache AGE on Postgres or Neo4j Community (ADR-0003,
Proposed). ``SqliteGraphStore`` is the local adapter until Postgres runs
(ADR-0008): nodes and edges with JSON properties, upserted by id.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel

# Node labels and relation types: plan Phase 3, KG task 2 ("part, revision, mating part,
# material, supplier, load case, test result"), plus the features and drawings they come from.
PART, REVISION, MATERIAL, FEATURE, DRAWING = "Part", "Revision", "Material", "Feature", "Drawing"
MATING_PART, SUPPLIER, LOAD_CASE, TEST_RESULT = "MatingPart", "Supplier", "LoadCase", "TestResult"
HAS_REVISION, MADE_OF, HAS_FEATURE, FROM_DRAWING = "HAS_REVISION", "MADE_OF", "HAS_FEATURE", "FROM_DRAWING"
# Defined for the plan's relations; nothing feeds them yet (no source data in R1 so far).
MATES_WITH, SUPPLIED_BY, LOADED_BY, TESTED_IN = "MATES_WITH", "SUPPLIED_BY", "LOADED_BY", "TESTED_IN"


class Node(BaseModel):
    id: str
    label: str
    props: dict[str, Any] = {}


class Edge(BaseModel):
    source: str
    relation: str
    target: str
    props: dict[str, Any] = {}


class GraphStore(Protocol):
    def upsert_node(self, node: Node) -> None: ...
    def upsert_edge(self, edge: Edge) -> None: ...
    def node(self, node_id: str) -> Node | None: ...
    def nodes(self, label: str) -> list[Node]: ...
    def out(self, node_id: str, relation: str) -> list[Node]: ...


_SCHEMA = """
CREATE TABLE IF NOT EXISTS node (id TEXT PRIMARY KEY, label TEXT NOT NULL, props TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS edge (source TEXT NOT NULL, relation TEXT NOT NULL, target TEXT NOT NULL,
                                 props TEXT NOT NULL, PRIMARY KEY (source, relation, target));
CREATE INDEX IF NOT EXISTS node_label ON node(label);
CREATE INDEX IF NOT EXISTS edge_target ON edge(target, relation);
"""


class SqliteGraphStore:
    def __init__(self, path: Path | str) -> None:
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.executescript(_SCHEMA)

    def upsert_node(self, node: Node) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO node VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET label = excluded.label, "
                "props = excluded.props",
                (node.id, node.label, json.dumps(node.props)),
            )

    def upsert_edge(self, edge: Edge) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO edge VALUES (?, ?, ?, ?) ON CONFLICT(source, relation, target) "
                "DO UPDATE SET props = excluded.props",
                (edge.source, edge.relation, edge.target, json.dumps(edge.props)),
            )

    def node(self, node_id: str) -> Node | None:
        row = self.db.execute("SELECT id, label, props FROM node WHERE id = ?", (node_id,)).fetchone()
        return Node(id=row[0], label=row[1], props=json.loads(row[2])) if row else None

    def nodes(self, label: str) -> list[Node]:
        rows = self.db.execute("SELECT id, label, props FROM node WHERE label = ? ORDER BY id", (label,))
        return [Node(id=r[0], label=r[1], props=json.loads(r[2])) for r in rows]

    def out(self, node_id: str, relation: str) -> list[Node]:
        rows = self.db.execute(
            "SELECT n.id, n.label, n.props FROM edge e JOIN node n ON n.id = e.target "
            "WHERE e.source = ? AND e.relation = ? ORDER BY n.id",
            (node_id, relation),
        )
        return [Node(id=r[0], label=r[1], props=json.loads(r[2])) for r in rows]

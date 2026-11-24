# ADR-0003: Graph store

| | |
|---|---|
| Status | Proposed |
| Date | 2026-11-24 |
| Phase | Phase 0, task 7 (plan §6 Phase 0); built in Phase 3 |

## Context

Block 3, the Knowledge Graph, sits next to block 2, Interpretation (plan §2.1). Its job in Phase 3 (plan Phase 3, Knowledge Graph):

1. Graph store: "Apache AGE in Postgres (keeps one database) or Neo4j Community if the team prefers Cypher tooling".
2. Entity relations: part, revision, mating part, material, supplier, load case, test result.
3. Similar-part search from text embeddings of design graphs plus trimesh shape descriptors.
4. Corroboration service for flagged values.

The library table lists "Apache AGE on Postgres or Neo4j Community", with the note: "Neo4j Community is GPLv3 and single-node; Apache AGE keeps the graph inside Postgres" (plan §4.2, block 3). The licence watch-list gives Neo4j Community "GPLv3, single node", with the decision "Separate service, or Apache AGE instead" (plan §9).

Related stores in the plan:

- PostgreSQL is the relational store and Run Store (plan §4.1).
- Vector search is pgvector: "Start in Postgres; move to Qdrant past ~10M vectors" (plan §4.1).
- The design graph in block 2 uses NetworkX (plan §4.2, block 2). Its evaluation uses a "NetworkX graph diff" (plan §7).
- Phase 7 keeps "mating interfaces fixed using Knowledge Graph relations" (plan Phase 7 task 1).

What the deck says:

- The Engineering Data Catalogue row lists "PostgreSQL with pgvector; graph tables in PostgreSQL; FastAPI; Parquet and JSON", status "Confirmed: PostgreSQL, pgvector" (deck slide 62).
- The Catalogue makes data answerable through "lineage, vector search, knowledge graph, cited answers" (deck slide 63).
- The Knowledge Graph is also listed as a pipeline component (deck slides 30, 32, 62).
- The Interpretation Engine stack has "NetworkX graph, pgvector similarity" (deck slide 65).

The deck does not name a graph extension or a graph database. It does not say whether "graph tables in PostgreSQL" means Apache AGE or plain relational tables. This difference is not logged in [plan-vs-deck.md](../reference/plan-vs-deck.md) and has no OD id.

## Options considered

| Option | Source | Notes |
|---|---|---|
| A. Apache AGE on PostgreSQL | plan §4.2 block 3, Phase 3, §9 | Listed first by the plan, which ranks neither option. "Keeps one database" (plan Phase 3). The plan does not state AGE's licence |
| B. Neo4j Community | plan §4.2 block 3, Phase 3, §9 | The plan's alternative, "if the team prefers Cypher tooling" (plan Phase 3). GPLv3, single node; runs as a separate service (plan §9) |
| C. "Graph tables in PostgreSQL" | deck slide 62 | Deck position. No engine named. Like A, it keeps the graph in PostgreSQL |

## Decision

Proposed: **Option A, Apache AGE on PostgreSQL** (plan §4.2 block 3, Phase 3). The plan gives the two as an either/or and does not rank them. It lists AGE first and makes Neo4j Community conditional on the team preferring Cypher tooling (plan Phase 3). This ADR proposes AGE on that basis. Neo4j Community would run as a separate service (plan §9).

The deck's position is "graph tables in PostgreSQL" (deck slide 62). It agrees with Option A on keeping the graph in PostgreSQL but does not name an engine. This ADR does not settle that difference.

## Consequences

- With Option A the graph stays inside PostgreSQL ("keeps one database", plan Phase 3; plan §4.2 block 3). Whether it shares one database instance with the Run Store and pgvector (plan §4.1) is not specified in plan or deck; TBD in Phase 0.
- If Option B is chosen, Neo4j Community runs as a separate service, not in-process, under the GPL rule (plan §9). It is single-node (plan §4.2, §9).
- The graph store is built in Phase 3, not Phase 1. Phase 1's Data Catalogue uses Postgres + pgvector, Marquez and the OpenLineage client (plan Phase 1). In the plan's assumed timeline, Phase 3 starts 2027-02-22 (plan §5).
- Code for block 3 goes in `blocks/b3_knowledge_graph/` (plan Appendix A).
- Phase 3 exit criteria apply to whichever store is chosen: at least 50 % of low-confidence flags on the golden set correctly resolved by corroboration, none resolved wrongly above 0.9 confidence, and similar-part search top-3 recall ≥ 0.8 on a curated set (plan Phase 3).
- Licences: Neo4j Community is GPLv3 (plan §4.2, §9). The licence of Apache AGE is not stated in the plan. Both licences are to be confirmed in the Phase 0 licence scan (plan §4 preamble, Phase 0 task 6).

## Open items

- Plan (Apache AGE or Neo4j Community) vs deck ("graph tables in PostgreSQL", deck slide 62): not logged in plan-vs-deck.md and no OD id yet. To be added to [open-decisions.md](../open-decisions.md) by its owner.
- Where the knowledge graph sits: the plan makes it pipeline block 3 (plan §2.1, Appendix A). The deck lists it under the Engineering Data Catalogue (deck slides 62, 63) and also as a pipeline component (deck slides 30, 32, 62). Not decided here; no OD id yet.
- Apache AGE licence: not stated in the plan. TBD in the Phase 0 licence scan (plan Phase 0 task 6).
- Team preference for Cypher tooling, which the plan gives as the reason to choose Neo4j (plan Phase 3): not recorded. TBD before Phase 3.
- Who accepts this ADR: not specified in plan or deck (see [README.md](README.md)).

## Sources

- Plan §2.1, §4 (preamble), §4.1, §4.2 (blocks 2 and 3), §5, §6 Phase 0 (tasks 6 and 7), Phase 1, Phase 3, Phase 7 (task 1), §7, §9, Appendix A.
- Deck slides 30, 32, 62, 63, 65.
- [plan-vs-deck.md](../reference/plan-vs-deck.md): this difference is not yet listed.
- [open-decisions.md](../open-decisions.md): no OD id yet.

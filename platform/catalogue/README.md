# Data Catalogue

**Status: Phase 1 local adapter built** ([ADR-0008](../../docs/adr/0008-local-first-adapters.md)).

| Built | Source |
|---|---|
| Artifact registry (run, block, version, kind, URI, schema version) | plan Phase 1 |
| Element-level lineage: every source locator of every artifact, in order; trace back from a file (`derived_from`) | plan Phase 1, principle 1 |
| `catalogue.lineage.recorded` event | plan Appendix B |
| HTTP: `GET /runs/{id}/artifacts`, `GET /artifacts/{id}/lineage`, `GET /files/{id}/derived` | |

**Cited answers (2026-11-25)**, `edp_catalogue.answer`: the run's artifacts become numbered facts, each with its source handles; the model is asked through the Model Gateway to answer only from them and to cite their ids. Citations are checked: ids that are not facts are dropped and flagged `UNKNOWN_CITATION`; an answer that claims support but cites nothing is flagged `UNCITED_ANSWER`. Served to the console as `POST /api/runs/{id}/chat`.

Not built yet: the vector index (embeddings, OD-42), so cited answers cover one run, not the whole catalogue; dataset-level lineage through OpenLineage into Marquez; PostgreSQL instead of SQLite (OD-21).

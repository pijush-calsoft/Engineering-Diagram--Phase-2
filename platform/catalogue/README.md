# Data Catalogue

**Status: Phase 1 local adapter built** ([ADR-0008](../../docs/adr/0008-local-first-adapters.md)).

| Built | Source |
|---|---|
| Artifact registry (run, block, version, kind, URI, schema version) | plan Phase 1 |
| Element-level lineage: every source locator of every artifact, in order; trace back from a file (`derived_from`) | plan Phase 1, principle 1 |
| `catalogue.lineage.recorded` event | plan Appendix B |
| HTTP: `GET /runs/{id}/artifacts`, `GET /artifacts/{id}/lineage`, `GET /files/{id}/derived` | |

Not built yet: the vector index and the "cited answer" endpoint (need an embedding model, OD-42); dataset-level lineage through OpenLineage into Marquez; PostgreSQL instead of SQLite (OD-21).

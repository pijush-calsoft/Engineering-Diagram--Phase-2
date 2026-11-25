# ADR-0008: Local-first adapters for platform services

| | |
|---|---|
| Status | **Accepted** 2026-11-24. The project owner said "ignore docker installation, start implementation" |
| Date | 2026-11-24 |
| Phase | Phase 1 |

## Context

Phase 1 stands up the Data Fabric, Data Catalogue, Model Gateway, orchestrator and console on SeaweedFS, lakeFS, NATS JetStream, PostgreSQL, Marquez, LiteLLM, Keycloak, step-ca, Langfuse and Temporal (plan Phase 1, §4.1). These normally run as containers. The platform runs locally (OD-2). No container runtime is installed yet (OD-21), and the owner asked to start implementation without it.

## Decision

Every external service sits behind a small interface. Phase 1 ships a **local adapter** for each one, so the walking skeleton runs with plain Python. The plan's service replaces the adapter later without changing callers.

| Concern | Plan's service (plan §4.1, Phase 1) | Local adapter now | Interface |
|---|---|---|---|
| Event bus | NATS JetStream (ADR-0002, OD-10) | In-memory bus | `edp_kit.events.EventBus` |
| Object storage and dataset versions | SeaweedFS + lakeFS (ADR-0004) | Filesystem zones `raw`, `cleaned`, `final`, with content-hash commit ids | `edp_fabric.FabricStore` |
| Catalogue store, element-level lineage | PostgreSQL (+ Marquez for dataset lineage) | SQLite (Python standard library) | `edp_catalogue.Catalogue` |
| Orchestrator checkpointer | LangGraph Postgres checkpointer (ADR-0001) | LangGraph SQLite checkpointer | LangGraph `Checkpointer` |
| Block transport | FastAPI service per block (plan §3) | In-process call; the same blocks are also served over HTTP by `edp_kit.service` | `Block` protocol |

Data Fabric URIs use the scheme `fabric://<zone>/<dataset>/<commit>/<file>` while the local adapter is in use. Plan §3 expects `s3://` paths inside the Fabric; they replace `fabric://` when SeaweedFS is in place.

## Consequences

- The walking skeleton (upload → run → eight stub results → lineage) runs and is tested without containers.
- Phase 1 exit criteria that name specific services cannot be met yet: lineage visible in Marquez, an end-to-end trace in Langfuse, and mTLS on every gateway call (plan Phase 1). They stay open until the services run.
- Temporal (durable long jobs, ADR-0001) is not needed until meshing and solver runs (Phase 5). The LangGraph checkpointer covers the Phase 1 restart criterion.
- Phase 1's "virus and type check" on upload: type detection from content is built; virus scanning is not, because no scanner has been chosen (OD-44).

## Open items

- OD-10 (event bus), OD-21 (container runtime): the real services replace the adapters when available.
- OD-44: virus scanner for uploads.

## Sources

- Plan §2.2, §3, §4.1, §6 Phase 1, Appendix B.
- [ADR-0001](0001-orchestrator.md), [ADR-0002](0002-event-bus.md), [ADR-0004](0004-object-storage.md).
- [open-decisions.md](../open-decisions.md): OD-2, OD-10, OD-21, OD-44.

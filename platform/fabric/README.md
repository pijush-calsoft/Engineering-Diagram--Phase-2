# Data Fabric

**Status: Phase 1 local adapter built** ([ADR-0008](../../docs/adr/0008-local-first-adapters.md)).

| Built | Source |
|---|---|
| Upload (`FabricStore.ingest`, `POST /files`) with type detection from content; extension is a hint, a mismatch gives a warning, unknown content fails with `unsupported_type` | plan Phase 1 "type check"; deck slide 42 |
| Zones `raw`, `cleaned`, `final`; promotion one zone at a time (`POST /datasets/{id}/promote`) | plan Phase 1 |
| Immutable commits; the commit id is `SourceLocator.version` | plan §4.1 lakeFS row; deck slide 39 |
| Events `fabric.file.ingested`, `fabric.dataset.versioned`, `fabric.dataset.promoted` with the Appendix B payloads | plan Appendix B |

Not built yet: the virus check on upload (OD-44), and SeaweedFS and lakeFS (needs a container runtime, OD-21). Local URIs use `fabric://` until `s3://` paths are available (ADR-0008).

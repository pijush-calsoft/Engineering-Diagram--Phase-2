# ADR-0004: Object storage and dataset versioning

| | |
|---|---|
| Status | Proposed |
| Date | 2026-11-24 |
| Phase | Phase 0, task 7 (plan §6 Phase 0); built in Phase 1 |

## Context

The Data Fabric receives all inputs (plan §2.1). The contract points into it:

- `Artifact.uri` is an "s3:// path inside the Data Fabric" (plan §3).
- `SourceLocator.version` is the "lakeFS commit or dataset version" (plan §3).

What the plan chooses (plan §4.1):

| Need | Primary choice | Licence | Alternative | Notes (as given in the plan) |
|---|---|---|---|---|
| Object storage | SeaweedFS (S3 API) | Apache 2.0 | Ceph RGW (LGPL) | "MinIO Community Edition is no longer maintained, so it is not used" |
| Dataset versioning (raw, cleaned, final) | lakeFS | Apache 2.0 | DVC (Apache 2.0) | "Git-like branches and commits over object storage; commit id becomes `SourceLocator.version`" |

The licence watch-list lists MinIO Community as "No longer maintained; AGPL", with the decision "Use SeaweedFS or Ceph RGW" (plan §9).

Phase 1 builds the Data Fabric: "Upload API, virus and type check, raw/cleaned/final zones as lakeFS branches, `fabric.*` events", on FastAPI, SeaweedFS, lakeFS, NATS JetStream and Postgres (plan Phase 1). Exit criterion: "A file uploaded in the console produces a versioned dataset" (plan Phase 1). The related events are `fabric.dataset.versioned` (payload includes the lakeFS commit) and `fabric.dataset.promoted` (from zone, to zone) (plan Appendix B).

Other constraints in the plan:

- Principle 7: "Client data stays in client scope" (plan §2.3).
- Risk 8 mitigation: "Tenant isolation, per-client storage and keys" (plan §10).
- Golden dataset manifests sit in `eval/golden/`; the data itself lives in the fabric (plan Appendix A).

What the deck says:

- Three zones: Raw (bronze), "Stored as received. Checksum. Immutable copy"; Cleaned (silver); Final (gold), "Approved, versioned" (deck slide 30).
- Storage layout: `/bronze/{workspace}/{project}/{drawing}/`, `/silver/.../{drawing}/`, `/gold/.../{dataset}/v{n}/`. "Raw files never change. A correction creates a new version". A stage scheduler picks up events (deck slide 39).
- Data Fabric stack: "Python workers; Airflow or Dagster; file and object storage", status "Confirmed: Python. Scheduler proposed" (deck slide 62).
- The Companion stores models and reports in an "Object store" (deck slide 47).

The deck does not name an object store product or a dataset versioning tool. The difference is logged as L2 ([plan-vs-deck.md](../reference/plan-vs-deck.md)).

## Options considered

| Option | Source | Notes |
|---|---|---|
| A. SeaweedFS (S3 API) for objects, lakeFS for dataset versions; zones as lakeFS branches | plan §4.1, Phase 1 | The plan's primary choice. Both Apache 2.0 (plan §4.1) |
| B. Ceph RGW for objects; DVC for dataset versions | plan §4.1 (alternatives) | Ceph RGW is LGPL; DVC is Apache 2.0 (plan §4.1). The plan lists them as separate alternatives for each row |
| C. Bronze/silver/gold path prefixes with `v{n}` folders, Python workers, Airflow or Dagster scheduler | deck slides 30, 39, 62 | Deck position, L2. No storage product named |
| Excluded: MinIO Community | plan §4.1, §9 | Not maintained; AGPL (plan §9) |

## Decision

Proposed: **Option A**. SeaweedFS (S3 API) is the object store and lakeFS is the dataset versioning layer, with the raw, cleaned and final zones as lakeFS branches (plan §4.1, Phase 1). The alternatives the plan lists are Ceph RGW for object storage and DVC for versioning (plan §4.1). MinIO Community is not used (plan §4.1, §9).

The deck's position is bronze/silver/gold paths with an Airflow or Dagster scheduler (L2, deck slides 39, 62). This ADR does not settle that difference.

## Consequences

- The contract already assumes this layout: `Artifact.uri` is an `s3://` path and `SourceLocator.version` carries the lakeFS commit (plan §3, §4.1). The plan lists SeaweedFS for its S3 API (plan §4.1).
- Zones are lakeFS branches (plan Phase 1). Promotion from one zone to the next emits `fabric.dataset.promoted`, and a new dataset version emits `fabric.dataset.versioned` with the lakeFS commit (plan Appendix B). The plan does not describe the promotion mechanism in more detail.
- If DVC replaces lakeFS, `SourceLocator.version` holds a dataset version instead of a lakeFS commit; the contract comment allows both (plan §3).
- The deck's zone names map to the plan's: raw = bronze, cleaned = silver, final = gold (deck slide 30).
- Licences: SeaweedFS and lakeFS are Apache 2.0 (plan §4.1), allowed anywhere under plan §9. Ceph RGW is LGPL (plan §4.1). Plan §9 says: "LGPL is allowed when used as a library without modification." How this rule applies to Ceph RGW, which the plan lists as an object store and not as a library (plan §4.1), is not specified in plan or deck; TBD in Phase 0 through the licence policy and scan (plan Phase 0 task 6) and, if flagged, legal review (plan §4 preamble). The licences of the candidate tools (SeaweedFS, lakeFS, Ceph RGW, DVC) are to be confirmed in the Phase 0 licence scan (plan §4 preamble, Phase 0 task 6). MinIO Community is on the watch-list and is not used (plan §9).
- Golden dataset files live in the fabric (plan Appendix A: "data lives in the fabric"). The repository rule keeps golden-set data out of git (plan-vs-deck D10).

## Open items

- L2 (deck bronze/silver/gold paths and Airflow or Dagster scheduler vs plan lakeFS branches): logged in plan-vs-deck.md but has no OD id in [open-decisions.md](../open-decisions.md) yet. To be added by its owner.
- Whether the Data Fabric needs a stage scheduler (deck slides 39, 62): the plan does not name one. Not decided here.
- How the plan §9 LGPL rule ("allowed when used as a library without modification") applies to Ceph RGW, which the plan lists as an object store and not as a library (plan §4.1): not specified in plan or deck. TBD in Phase 0 through the licence policy and scan (plan Phase 0 task 6) and, if flagged, legal review (plan §4 preamble).
- How per-client storage and keys are set up (plan §10 risk 8): not specified in plan or deck. TBD.
- Storage capacity and sizing: not specified in plan or deck. Phase 0 task 8 covers GPU and CPU only (OD-20).
- Hosting model, which affects where storage runs: OD-2.
- Container build is blocked until Docker is available (OD-21).
- Who accepts this ADR: not specified in plan or deck (see [README.md](README.md)).

## Sources

- Plan §2.1, §2.3 (principle 7), §3, §4 (preamble), §4.1, §6 Phase 0 (tasks 6 and 7), Phase 1, §9, §10 (risk 8), Appendix A, Appendix B.
- Deck slides 30, 39, 47, 62.
- [plan-vs-deck.md](../reference/plan-vs-deck.md): L2, D10.
- [open-decisions.md](../open-decisions.md): OD-2, OD-20, OD-21.
- Code: `contracts/src/edp_contracts/block.py` (`SourceLocator.version`, `Artifact.uri`).

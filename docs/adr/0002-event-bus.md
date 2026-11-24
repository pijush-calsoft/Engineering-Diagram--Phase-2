# ADR-0002: Event bus

| | |
|---|---|
| Status | Proposed. On 2026-11-24 the owner answered OD-10 with "we will install" without naming a broker, so the plan's NATS JetStream is the working choice until confirmed |
| Date | 2026-11-24 |
| Phase | Phase 0, task 7 (plan §6 Phase 0) |

## Context

Blocks publish `run.block.started`, `run.block.completed` and `run.block.failed`. The Data Fabric publishes `fabric.file.ingested`, `fabric.dataset.versioned` and `fabric.dataset.promoted` (plan §3). The full subject list, with emitters and payloads, is in plan Appendix B. It also covers `run.planned`, `catalogue.lineage.recorded`, `review.requested` / `review.resolved` and `twin.state.updated` / `twin.alert.raised`.

What the plan chooses:

| Source | Choice | Alternative | Notes |
|---|---|---|---|
| plan §2.2 | NATS JetStream (Apache 2.0) | none listed | "Lightweight, persistent streams for `fabric.*` and `run.*` events" |
| plan §4.1 | NATS JetStream, Apache 2.0 | Apache Kafka (Apache 2.0) | "`fabric.*`, `run.*`, `twin.*` subjects" |

Where the plan uses it:

- Phase 1: the Data Fabric emits `fabric.*` events, with NATS JetStream in its stack. The console pipeline map shows "live block status from `run.*` events" (plan Phase 1).
- Phase 8: "MQTT (Mosquitto) and OPC UA (asyncua) into NATS, then the Data Fabric" (plan Phase 8 task 1).
- Cache and queues are a separate concern. The plan uses Valkey (BSD-3) for them, because Redis 8+ is AGPL/SSPL/RSAL tri-licensed (plan §4.1, §9).

What the deck says:

- Controller stores include Kafka (deck slide 38).
- Messaging row: "Kafka for events; Valkey (Redis-compatible) for jobs and cache; Apache Pulsar as an option", status "Kafka confirmed; Valkey (Redis-compatible) replaces Redis. Valkey and Pulsar proposed" (deck slide 62).
- "Kafka: events between stages; scales by partitions". "Apache Pulsar: option for separate tenants (Phase 2)". "One queue adapter, so the choice is configuration" (deck slide 64).
- Twin sensor streams go through Kafka (deck slides 65, 74).
- "Events on Kafka carry IDs and pointers, never drawing or model content" (deck slide 95).

The broker difference is logged as D5. The deck also uses different event names (I2, deck slides 39, 95) ([plan-vs-deck.md](../reference/plan-vs-deck.md)).

## Options considered

| Option | Source | Notes |
|---|---|---|
| A. NATS JetStream | plan §2.2, §4.1, Phase 1 | The plan's primary choice. Apache 2.0 (plan §4.1) |
| B. Apache Kafka | plan §4.1 (alternative); deck slides 38, 62, 64, 95 | The plan's alternative. Apache 2.0 (plan §4.1). The deck marks it "Kafka confirmed" (deck slide 62). D5 |
| C. Apache Pulsar | deck slides 62, 64 | Deck only, "as an option" and "option for separate tenants (Phase 2)". Not in the plan. Its licence is not stated in plan or deck |

## Decision

Proposed: **Option A, NATS JetStream**, for the `fabric.*`, `run.*` and `twin.*` subjects (plan §2.2, §4.1). The alternative the plan lists is Apache Kafka (plan §4.1).

The deck's position is Kafka, with Pulsar as an option (D5, deck slides 62, 64). That choice is open as OD-10 and this ADR does not settle it.

Plan and deck agree on Valkey for cache and job queues (plan §4.1, deck slides 62, 64). That is not part of this decision.

## Consequences

- Subject names are kept as plain strings in `edp_contracts.events`, taken from plan §3 and Appendix B. No broker client library has been added (plan-vs-deck D5). Whether the subject names stay the same under another broker is not specified in plan or deck; naming is open under OD-15.
- Phase 1 publishes `fabric.*` events from the Data Fabric on NATS JetStream and reads `run.*` events for the console's live block status (plan Phase 1).
- Phase 8 signal ingest is planned as MQTT and OPC UA "into NATS" (plan Phase 8 task 1). If Kafka is chosen, that step changes. The deck routes sensor streams through Kafka (deck slides 65, 74).
- Licences: NATS JetStream and Kafka are both Apache 2.0 (plan §4.1), which plan §9 allows anywhere. Both are to be confirmed in the Phase 0 licence scan (plan §4 preamble, Phase 0 task 6).
- Appendix B payloads are mostly identifiers (for example file id, hash, lakeFS commit, run id). Some carry more: `run.block.*` carries metrics and flags, `review.*` carries reviewer and decision, and `twin.*` carries state, life estimate and alert (plan Appendix B). The deck states "IDs and pointers, never drawing or model content" as a rule (deck slide 95). The plan does not state it as a rule.

## Open items

- OD-10: NATS JetStream (plan) or Kafka (deck). Open.
- OD-15: event subject names. The plan's Appendix B names or the deck's names (I2, deck slides 39, 95). Open.
- A queue or broker adapter so that "the choice is configuration" (deck slide 64): not addressed in the plan. Not decided here.
- Apache Pulsar for separate tenants (deck slide 64): not in the plan; no OD id yet. Its licence is not specified in plan or deck.
- Whether "IDs and pointers only" becomes a rule for event payloads (deck slide 95): not in the plan; no OD id yet.
- Who accepts this ADR: not specified in plan or deck (see [README.md](README.md)).

## Sources

- Plan §2.2, §3, §4 (preamble), §4.1, §6 Phase 0 (tasks 6 and 7), Phase 1, Phase 8 (task 1), §9, Appendix B.
- Deck slides 38, 39, 62, 64, 65, 74, 95.
- [plan-vs-deck.md](../reference/plan-vs-deck.md): D5, I2.
- [open-decisions.md](../open-decisions.md): OD-10, OD-15.
- Code: `contracts/src/edp_contracts/events.py`.

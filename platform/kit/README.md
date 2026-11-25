# edp-kit: shared service kit

**Status: built (Phase 1).** Not in plan Appendix A; added so every service shares one event bus and one block-serving path ([ADR-0008](../../docs/adr/0008-local-first-adapters.md)).

| Module | Content | Source |
|---|---|---|
| `edp_kit.events` | `EventBus` interface and `InMemoryEventBus`. Only subjects from `edp_contracts.events` can be published | plan §2.2, Appendix B |
| `edp_kit.service` | `run_block()`, which publishes `run.block.started`, `completed` and `failed`; `create_block_app()`, which serves any block on `POST /run`, `GET /health` and `GET /contract` | plan §3 |

NATS JetStream replaces the in-memory bus when it runs (ADR-0002, OD-10).

# Orchestrator

**Status: Phase 1 skeleton built** ([ADR-0001](../docs/adr/0001-orchestrator.md), [ADR-0008](../docs/adr/0008-local-first-adapters.md)).

| Built | Source |
|---|---|
| LangGraph graph: planner node (`run.planned`), then one node per block in R1 pipeline order | plan §2.2, Phase 1, Appendix B |
| Stub blocks 1 to 8 (`stub_blocks()`); outputs carry their inputs' source locators | plan Phase 1 "stub nodes for blocks 1 to 8" |
| SQLite checkpointer. A run that stops on an error resumes from the last completed block, also from a new process | plan Phase 1 exit criterion "Restarting any block mid-run resumes from the checkpoint" |
| Human review: a `needs_review` result pauses the run; `review(run_id, "approve" or "reject", reviewer)` continues or stops it | plan Phase 1 "interrupt points for human review", principle 3 |

Try it:

```
uv run python -m edp_orchestrator --file eval/golden/data/synthetic/syn-iso-plate-000.dxf --data-dir var
```

Not built yet: planning from chat through the Model Gateway (needs OD-43 models); the Postgres checkpointer and Temporal workers (OD-21, Phase 5). The orchestrator does not emit `review.*` events, because Appendix B assigns them to the console.

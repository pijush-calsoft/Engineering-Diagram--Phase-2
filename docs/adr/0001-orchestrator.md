# ADR-0001: Orchestrator

| | |
|---|---|
| Status | **Accepted** 2026-11-24. The project owner answered "yes" to OD-9. That is recorded as confirming the plan's option (Python LangGraph + Temporal), not the deck's Java Controller. Correct this if it was meant otherwise |
| Date | 2026-11-24 |
| Phase | Phase 0, task 7 (plan §6 Phase 0) |

## Context

The plan describes "a chat-driven orchestrator" that plans each request and hands work to specialised agents, "one Python service per pipeline block, all behind a shared plug-in contract" (plan §1).

The plan's runtime view (plan §2.2):

| Concern | Choice | Why (as given in the plan) |
|---|---|---|
| Agent orchestration | LangGraph (planner graph, per-block nodes, Postgres checkpointer) | Explicit state machine, human-in-the-loop interrupts, parallel branches, replayable runs |
| Durable long jobs (meshing, solver runs, DoE batches) | Temporal (MIT) | Retries, timeouts and resumption for jobs that run minutes to hours; keeps LangGraph state small |

Phase 1 builds the orchestrator as a "LangGraph planner graph with stub nodes for blocks 1 to 8, Postgres checkpointer, interrupt points for human review", with a "Temporal worker for long jobs" (plan Phase 1). One Phase 1 exit criterion is: "Restarting any block mid-run resumes from the checkpoint" (plan Phase 1).

Later phases rely on it:

- Phase 5: "Durable execution through Temporal so long runs survive restarts"; DoE "batch submission through Ray or Temporal" (plan Phase 5).
- The orchestrator emits `run.planned` (plan Appendix B).
- The console streams LangGraph events over FastAPI SSE or WebSockets (plan §4.3).
- Orchestrator evaluation: "Plan correctness on scripted chat scenarios, recovery from failures", using LangGraph tests and Langfuse datasets (plan §7).

The deck has a different design. Tier 2 is a "Controller (Java), the integrator" holding the plug-in registry, licence check, RBAC, workflow and review gates, job queue and audit log (deck slide 32). It "holds no state" (deck slide 32) and is "stateless, so it scales by adding copies" (deck slide 63). Its modules include a Workflow Engine and a Job Orchestrator, with stores PostgreSQL, Kafka and Valkey, and repositories through JPA (deck slide 38). The tech stack row reads "Java (current LTS), Spring Boot, JPA, circuit breakers, OAuth2 / OIDC tokens", status "Confirmed: Java. Spring Boot proposed" (deck slide 62). This difference is logged as D3 ([plan-vs-deck.md](../reference/plan-vs-deck.md)).

## Options considered

| Option | Source | Notes |
|---|---|---|
| A. LangGraph planner graph with a Postgres checkpointer, plus Temporal for durable long jobs, in Python | plan §2.2, Phase 1 | The plan's primary choice. Temporal is MIT (plan §2.2) |
| B. Java Controller (current LTS), Spring Boot proposed, JPA, stateless, with Workflow Engine and Job Orchestrator modules | deck slides 32, 38, 62, 63 | D3. The deck marks Java "Confirmed" and Spring Boot "proposed" (deck slide 62) |

The plan lists no alternative to LangGraph for agent orchestration. For DoE batch fan-out only, it names Ray alongside Temporal (plan §4.2 block 7, Phase 5).

## Decision

Proposed: **Option A**. LangGraph is the agent orchestrator (planner graph, per-block nodes, Postgres checkpointer, interrupt points for human review), and Temporal runs durable long jobs (plan §2.2, Phase 1).

The plan names no alternative orchestrator. The deck's position is a Java Controller (D3, deck slides 32, 38, 62). That choice is open as OD-9 and this ADR does not settle it.

## Consequences

- Phase 1 builds a LangGraph planner graph with stub nodes for blocks 1 to 8, a Postgres checkpointer, interrupt points for human review, and a Temporal worker (plan Phase 1).
- Code goes in `orchestrator/` ("LangGraph graphs, Temporal workflows", plan Appendix A). No Java module is created until OD-9 is decided (plan-vs-deck D3).
- The checkpointer uses PostgreSQL, which the plan already uses as the Run Store (plan §2.2, §4.1).
- Long-running work (meshing, solver runs, DoE batches) goes through Temporal so that LangGraph state stays small (plan §2.2, Phase 5).
- Human review is an interrupt point in the graph (plan Phase 1). The approval workflow for write-backs (approve, reject, comment) is a separate console task in Phase 7 (plan Phase 7 task 5).
- Licences: the plan gives Temporal as MIT (plan §2.2). The plan lists LangGraph under block 2 as "All permissive" but names no specific licence (plan §4.2 block 2). Both licences are to be confirmed in the Phase 0 licence scan (plan §4 preamble, Phase 0 task 6).
- If Option B were chosen, the deck puts more in the Controller than the plan puts in the orchestrator: plug-in registry, licence check, RBAC and audit log (deck slides 32, 38). This touches other logged differences: roles (L5) and plug-in endpoints and manifest (I1, OD-15). The deck also says the View "Talks to the Controller only" (deck slide 32) and the screens "call the Controller only" (deck slide 63). That point is not logged in plan-vs-deck.md.

## Open items

- OD-9: LangGraph + Temporal (plan) or Java Spring Boot Controller (deck). Open.
- OD-15: plug-in contract endpoints; the deck Controller expects `/status` and `/result` (deck slide 38, I1). Open.
- LangGraph exact licence: not named in the plan (plan §4.2 block 2 says "All permissive"). TBD in the Phase 0 licence scan (plan Phase 0 task 6).
- Whether DoE batch fan-out uses Ray or Temporal: the plan allows both (plan Phase 5). Not decided here.
- Who accepts this ADR: not specified in plan or deck (see [README.md](README.md)).

## Sources

- Plan §1, §2.2, §4 (preamble), §4.1, §4.2 (blocks 2 and 7), §4.3, §6 Phase 0 (tasks 6 and 7), Phase 1, Phase 5, Phase 7 (task 5), §7, Appendix A, Appendix B.
- Deck slides 32, 38, 62, 63.
- [plan-vs-deck.md](../reference/plan-vs-deck.md): D3, I1, L5.
- [open-decisions.md](../open-decisions.md): OD-9, OD-15.

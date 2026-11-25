# Architecture decision records

Phase 0 task 7 of the plan asks to "record architecture decisions as ADRs: orchestrator, event bus, graph store, object storage, model hosting" (plan §6 Phase 0). The Phase 0 deliverables list "ADRs 001 to 008" (plan §6 Phase 0).

New ADRs start from [0000-template.md](0000-template.md).

## Index

| Number | Title | Status | Date | Open decisions referenced |
|---|---|---|---|---|
| [0000](0000-template.md) | ADR template | n/a | 2026-11-24 | |
| [0001](0001-orchestrator.md) | Orchestrator | **Accepted** | 2026-11-24 | OD-9 (decided), OD-15 |
| [0002](0002-event-bus.md) | Event bus | **Accepted** | 2026-11-25 | OD-10, OD-15 |
| [0003](0003-graph-store.md) | Graph store | Proposed | 2026-11-24 | None yet (see the ADR) |
| [0004](0004-object-storage.md) | Object storage and dataset versioning | Proposed | 2026-11-24 | OD-2, OD-20, OD-21. None yet for L2 (see the ADR) |
| [0005](0005-model-hosting.md) | Model hosting | **Accepted, amended**: hosted APIs only, OpenAI | 2026-11-24 | OD-5, OD-11, OD-37 (decided), OD-39, OD-43 |
| [0006](0006-r2-write-back-targets.md) | First write-back targets for R2 | **Accepted** | 2026-11-24 | OD-4 (decided) |
| [0007](0007-vision-via-multimodal-api.md) | Vision, OCR and symbol reading through a multimodal LLM API | **Accepted** | 2026-11-24 | OD-38 (decided), OD-39, OD-42, OD-43 |
| [0008](0008-local-first-adapters.md) | Local-first adapters for platform services | **Accepted** | 2026-11-25 | OD-10, OD-21, OD-44 |

## Reserved numbers

All eight slots the plan asks for are now used: ADR-0006 to 0008 record OD-4, OD-38 and the local-first adapters. The plan asks for ADRs 001 to 008 but names only five topics (plan §6 Phase 0, task 7 and deliverables). The other three topics are not specified in the plan or deck; see OD-19.

## Status

| Status | Meaning |
|---|---|
| Proposed | Written from the plan and deck. Not signed off |
| Accepted | Signed off by the deciding owner. Owner role and date recorded in [open-decisions.md](../open-decisions.md) |
| Superseded | Replaced by a later ADR, named in the Status line |

ADR-0001, 0005, 0006, 0007 and 0008 are **Accepted** from the project owner's answers on 2026-11-24, and ADR-0002 on 2026-11-25 (see [open-decisions.md](../open-decisions.md)). ADR-0003 and 0004 are **Proposed**. Each proposal states the plan's primary choice as the proposal (for the graph store, which the plan does not rank, the option it lists first; see ADR-0003), because the plan is the baseline in this repository ([plan-vs-deck.md](../reference/plan-vs-deck.md)). For every topic the deck says something different or less specific; each ADR records the deck position with its slide numbers.

Plan §8 gives "Contract, ADRs, orchestrator, reviews" to the tech lead / architect role. Neither the plan nor the deck says who accepts an ADR. The project owner's answers of 2026-11-24 are treated as acceptance for the ADRs they decide; the rest stay Proposed.

## Numbering

The plan writes ADR numbers with three digits (001 to 008). Files here use four digits (`0001-...`). ADR-0001 is the plan's ADR 001, and so on.

"""Orchestrator: LangGraph planner graph over the block pipeline (plan §2.2, Phase 1; ADR-0001).

- Planner node publishes ``run.planned`` with run id, stages and blocks (Appendix B).
  It runs the R1 pipeline in order; planning from chat through the Model
  Gateway comes later.
- One node per block, called through ``edp_kit.run_block``, which publishes the
  ``run.block.*`` events. Outputs are registered in the Data Catalogue with
  their source locators.
- Checkpointer: SQLite locally, Postgres later (ADR-0008). A run that stops on
  an error resumes from the last completed block (plan Phase 1 exit criterion).
- Human review: a block result with status ``needs_review`` pauses the run
  before the next block until a reviewer decides (plan Phase 1 "interrupt
  points for human review", principle 3).
"""

import operator
import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from edp_catalogue import Catalogue
from edp_contracts import Artifact, Block, BlockRequest
from edp_contracts.events import RUN_PLANNED
from edp_kit import EventBus, run_block

INPUT = "input"
REVIEW = "review"


class RunState(TypedDict, total=False):
    run_id: str
    artifacts: Annotated[list[dict[str, Any]], operator.add]  # {"block", "catalogue_id", "artifact"}
    results: Annotated[list[dict[str, Any]], operator.add]  # {"block", "status", "flags", "metrics"}
    pending_next: str | None
    decision: dict[str, str] | None


class RunStatus(BaseModel):
    run_id: str
    state: Literal["completed", "awaiting_review", "stopped", "rejected", "unknown"]
    next: list[str]
    results: list[dict[str, Any]]
    error: str | None = None


class Orchestrator:
    def __init__(
        self, blocks: Sequence[Block], catalogue: Catalogue, bus: EventBus, checkpoint_path: Path | str
    ) -> None:
        self.blocks = list(blocks)
        self.catalogue = catalogue
        self.bus = bus
        self._conn = sqlite3.connect(checkpoint_path, check_same_thread=False)
        self.app = self._build().compile(checkpointer=SqliteSaver(self._conn), interrupt_before=[REVIEW])

    # --- public API -------------------------------------------------------------------

    def start(self, run_id: str, inputs: Sequence[Artifact]) -> RunStatus:
        if self.app.get_state(self._config(run_id)).values:
            raise ValueError(f"run {run_id!r} already exists; use resume()")
        initial: RunState = {
            "run_id": run_id,
            "artifacts": [
                {"block": INPUT, "catalogue_id": None, "artifact": a.model_dump(mode="json")} for a in inputs
            ],
            "results": [],
            "pending_next": None,
            "decision": None,
        }
        return self._invoke(run_id, initial)

    def resume(self, run_id: str) -> RunStatus:
        """Continue a stopped run from its last checkpoint."""
        return self._invoke(run_id, None)

    def review(self, run_id: str, decision: Literal["approve", "reject"], reviewer: str) -> RunStatus:
        if REVIEW not in self.app.get_state(self._config(run_id)).next:
            raise ValueError(f"run {run_id!r} is not waiting for review")
        self.app.update_state(
            self._config(run_id), {"decision": {"decision": decision, "reviewer": reviewer}}
        )
        return self._invoke(run_id, None)

    def status(self, run_id: str, error: str | None = None) -> RunStatus:
        snap = self.app.get_state(self._config(run_id))
        values = snap.values or {}
        nxt = list(snap.next)
        decision = (values.get("decision") or {}).get("decision")
        if not values:
            state = "unknown"
        elif decision == "reject" and not nxt:
            state = "rejected"
        elif REVIEW in nxt:
            state = "awaiting_review"
        elif nxt:
            state = "stopped"
        else:
            state = "completed"
        return RunStatus(run_id=run_id, state=state, next=nxt, results=values.get("results", []), error=error)

    # --- graph ------------------------------------------------------------------------

    def _invoke(self, run_id: str, payload: RunState | None) -> RunStatus:
        try:
            self.app.invoke(payload, self._config(run_id))
        except Exception as exc:  # the checkpoint keeps every completed block
            return self.status(run_id, error=f"{type(exc).__name__}: {exc}")
        return self.status(run_id)

    @staticmethod
    def _config(run_id: str) -> RunnableConfig:
        return {"configurable": {"thread_id": run_id}}

    def _build(self) -> StateGraph:
        names = [b.name for b in self.blocks]
        g = StateGraph(RunState)
        g.add_node("planner", self._planner)
        for i, block in enumerate(self.blocks):
            nxt = names[i + 1] if i + 1 < len(names) else END
            g.add_node(block.name, self._block_node(block, nxt))
            g.add_conditional_edges(block.name, self._after_block, [REVIEW, nxt])
        g.add_node(REVIEW, self._review)
        g.add_conditional_edges(REVIEW, self._after_review, [*names, END])
        g.add_edge(START, "planner")
        g.add_edge("planner", names[0])
        return g

    def _planner(self, state: RunState) -> dict[str, Any]:
        stages = [b.name for b in self.blocks]
        self.bus.publish(
            RUN_PLANNED,
            {"run_id": state["run_id"], "stages": stages, "blocks": {b.name: b.version for b in self.blocks}},
        )
        return {}

    def _block_node(self, block: Block, nxt: str):  # noqa: ANN202 - LangGraph node
        def node(state: RunState) -> dict[str, Any]:
            run_id = state["run_id"]
            inputs = _select_inputs(state.get("artifacts", []), block.accepts)
            if not inputs:
                raise ValueError(f"no input of kinds {sorted(block.accepts)} for {block.name}")
            result = run_block(block, BlockRequest(run_id=run_id, inputs=inputs), self.bus)
            if result.status == "failed":
                raise RuntimeError(f"block {block.name} failed: {[f.message for f in result.flags]}")
            produced = [
                {
                    "block": block.name,
                    "catalogue_id": self.catalogue.register(run_id, block.name, block.version, a),
                    "artifact": a.model_dump(mode="json"),
                }
                for a in result.outputs
            ]
            record = {
                "block": block.name,
                "status": result.status,
                "metrics": result.metrics,
                "flags": [f.model_dump(mode="json") for f in result.flags],
            }
            return {"artifacts": produced, "results": [record], "pending_next": nxt, "decision": None}

        return node

    @staticmethod
    def _after_block(state: RunState) -> str:
        last = state["results"][-1]
        return REVIEW if last["status"] == "needs_review" else (state.get("pending_next") or END)

    @staticmethod
    def _review(state: RunState) -> dict[str, Any]:
        if not state.get("decision"):
            raise RuntimeError("review node reached without a decision")
        return {}

    @staticmethod
    def _after_review(state: RunState) -> str:
        decision = state.get("decision") or {}
        if decision.get("decision") != "approve":
            return END
        return state.get("pending_next") or END


def _select_inputs(artifacts: list[dict[str, Any]], accepts: set[str]) -> list[Artifact]:
    """Per accepted kind: pipeline outputs if any exist, otherwise the run's uploaded inputs."""
    chosen: list[Artifact] = []
    for kind in sorted(accepts):
        of_kind = [a for a in artifacts if a["artifact"]["kind"] == kind]
        produced = [a for a in of_kind if a["block"] != INPUT]
        chosen.extend(Artifact.model_validate(a["artifact"]) for a in (produced or of_kind))
    return chosen

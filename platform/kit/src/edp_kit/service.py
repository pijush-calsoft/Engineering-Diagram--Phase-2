"""Run a block and serve it over HTTP (plan §3).

Each block service exposes ``POST /run``, ``GET /health`` and ``GET /contract``,
and publishes ``run.block.started``, ``run.block.completed`` and
``run.block.failed`` with run id, block, version, metrics and flags
(Appendix B). The MCP tool with the same signature comes later (``mcp/``).
"""

from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from edp_contracts import Block, BlockContract, BlockRequest, BlockResult
from edp_contracts.events import RUN_BLOCK_COMPLETED, RUN_BLOCK_FAILED, RUN_BLOCK_STARTED
from edp_kit.events import EventBus


def _payload(block: Block, run_id: str, **extra: Any) -> dict[str, Any]:
    return {"run_id": run_id, "block": block.name, "version": block.version, **extra}


def run_block(block: Block, req: BlockRequest, bus: EventBus | None = None) -> BlockResult:
    """Run ``block`` on ``req`` and publish its run events. Exceptions are re-raised."""
    wrong = [a.kind for a in req.inputs if a.kind not in block.accepts]
    if wrong:
        raise ValueError(f"block {block.name!r} does not accept artifact kinds {wrong}")
    if bus:
        bus.publish(RUN_BLOCK_STARTED, _payload(block, req.run_id))
    try:
        result = block.run(req)
    except Exception as exc:
        if bus:
            bus.publish(RUN_BLOCK_FAILED, _payload(block, req.run_id, error=f"{type(exc).__name__}: {exc}"))
        raise
    if bus:
        flags = [f.model_dump() for f in result.flags]
        subject = RUN_BLOCK_FAILED if result.status == "failed" else RUN_BLOCK_COMPLETED
        bus.publish(
            subject, _payload(block, req.run_id, status=result.status, metrics=result.metrics, flags=flags)
        )
    return result


def create_block_app(
    block: Block, bus: EventBus | None = None, schema_versions: dict[str, str] | None = None
) -> FastAPI:
    app = FastAPI(title=f"EDP block: {block.name}", version=block.version)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "block": block.name, "version": block.version}

    @app.get("/contract")
    def contract() -> BlockContract:
        return BlockContract.of(block, schema_versions)

    @app.post("/run", response_model=BlockResult)
    def run(req: BlockRequest) -> BlockResult | JSONResponse:
        try:
            return run_block(block, req, bus)
        except ValueError as exc:
            return JSONResponse(status_code=422, content={"detail": str(exc)})
        except Exception as exc:
            return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})

    return app

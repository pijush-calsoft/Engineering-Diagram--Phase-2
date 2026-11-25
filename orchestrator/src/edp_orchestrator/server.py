"""Local console API (plan Phase 1 console shell, §4.3 "FastAPI SSE ... carrying LangGraph events").

One process serves the console and fronts the Data Fabric, Data Catalogue and
orchestrator, using the local adapters (ADR-0008). Blocks registered through the
``edp.blocks`` entry point replace the stubs; the rest stay stubs.

The chat panel asks the Data Catalogue for cited answers about a run, through the Model
Gateway (ADR-0009). Sample drawings are synthetic data; uploads are treated as client data
(OD-39): their text is redacted like any other, and their images would be refused.

Usage: ``uv run python -m edp_orchestrator.server --data-dir var [--port 8765] [--golden DIR ...]``
"""

import argparse
import json
import os
import threading
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from edp_catalogue import Catalogue
from edp_catalogue.answer import CitedAnswer, Turn, cited_answer, facts_from_run
from edp_contracts import Block
from edp_contracts.registry import discover_blocks
from edp_fabric import FabricStore, IngestResult, UnsupportedTypeError
from edp_gateway import DataClass, Gateway, GatewayConfig, GatewayError
from edp_kit import InMemoryEventBus
from edp_orchestrator.graph import Orchestrator, RunStatus
from edp_orchestrator.stubs import stub_blocks

CONSOLE_DIST = Path(__file__).resolve().parents[3] / "console" / "dist"
POLL_SECONDS = 0.2
SAMPLE_SUFFIXES = {".dxf", ".dwg", ".pdf", ".step", ".stp", ".igs", ".iges", ".stl"}
SAMPLE_SUFFIXES |= {".png", ".jpg", ".jpeg", ".tif", ".tiff"}  # scans (ADR-0007)


class StartedRun(BaseModel):
    run_id: str
    upload: IngestResult


class ReviewDecision(BaseModel):
    decision: Literal["approve", "reject"]
    reviewer: str


class BlockInfo(BaseModel):
    name: str
    version: str
    real: bool


class ChatStatus(BaseModel):
    available: bool
    reason: str | None = None
    model: str | None = None


class ChatQuestion(BaseModel):
    question: str
    history: list[Turn] = []


class Spend(BaseModel):
    spent_usd: float
    calls: int


class RunView(BaseModel):
    status: RunStatus
    running: bool
    upload: IngestResult | None
    artifacts: list[dict]


class Console:
    def __init__(
        self, data_dir: Path, golden: Path | list[Path] | None = None, gateway: Gateway | None = None
    ) -> None:
        data_dir.mkdir(parents=True, exist_ok=True)
        os.environ["EDP_DATA_DIR"] = str(data_dir)  # entry-point blocks share this Fabric
        self.bus = InMemoryEventBus()
        self.fabric = FabricStore(data_dir / "fabric", self.bus)
        self.catalogue = Catalogue(data_dir / "catalogue.sqlite", self.bus)
        real = discover_blocks()
        self.blocks: list[Block] = [real.get(b.name, b) for b in stub_blocks()]
        self.real = set(real)
        self.orchestrator = Orchestrator(
            self.blocks, self.catalogue, self.bus, data_dir / "checkpoints.sqlite"
        )
        self.golden = [golden] if isinstance(golden, Path) else list(golden or [])
        self.lock = threading.Lock()
        self.running: set[str] = set()
        self.uploads: dict[str, IngestResult] = {}
        self.data_class: dict[str, DataClass] = {}
        self._gateway = gateway

    def gateway(self) -> Gateway:
        """The Model Gateway, created on first use from ``.env`` (it needs ``OPENAI_API_KEY``)."""
        if self._gateway is None:
            self._gateway = Gateway(GatewayConfig.load())
        return self._gateway

    def chat_status(self) -> ChatStatus:
        try:
            cfg = self.gateway().config
        except Exception as exc:  # noqa: BLE001 - any configuration problem disables chat
            return ChatStatus(available=False, reason=f"Model Gateway not configured: {type(exc).__name__}")
        if not cfg.api_key:
            return ChatStatus(available=False, reason="Set OPENAI_API_KEY in .env to ask questions")
        if "text" not in cfg.models:
            return ChatStatus(available=False, reason="Set EDP_LLM_MODEL_TEXT in .env to ask questions")
        return ChatStatus(available=True, model=cfg.models["text"])

    def artifact_json(self, run_id: str, kind: str) -> dict | None:
        for r in self.catalogue.by_run(run_id):
            if r.artifact.kind == kind and r.artifact.uri.startswith("fabric://"):
                return json.loads(self.fabric.read(r.artifact.uri))
        return None

    def ask(self, run_id: str, q: ChatQuestion) -> CitedAnswer:
        status = self.orchestrator.status(run_id)
        flags = [f for r in status.results for f in r.get("flags", [])]
        facts = facts_from_run(
            self.artifact_json(run_id, "geometry"),
            self.artifact_json(run_id, "design_graph"),
            self.artifact_json(run_id, "similar_parts"),
            flags,
        )
        return cited_answer(
            self.gateway(), q.question, facts, self.data_class.get(run_id, "client"), run_id, q.history
        )

    def start(self, filename: str, data: bytes, data_class: DataClass = "client") -> StartedRun:
        upload = self.fabric.ingest(filename, data, uploader="console")
        run_id = f"run-{uuid.uuid4().hex[:8]}"
        self.uploads[run_id] = upload
        self.data_class[run_id] = data_class
        self.running.add(run_id)
        threading.Thread(
            target=self._work,
            args=(
                run_id,
                lambda: self.orchestrator.start(run_id, [upload.as_artifact()], {"data_class": data_class}),
            ),
            daemon=True,
        ).start()
        return StartedRun(run_id=run_id, upload=upload)

    def review(self, run_id: str, decision: ReviewDecision) -> None:
        self.running.add(run_id)
        threading.Thread(
            target=self._work,
            args=(run_id, lambda: self.orchestrator.review(run_id, decision.decision, decision.reviewer)),
            daemon=True,
        ).start()

    def _work(self, run_id: str, fn) -> None:  # noqa: ANN001
        try:
            with self.lock:
                fn()
        finally:
            self.running.discard(run_id)

    def view(self, run_id: str) -> RunView:
        status = self.orchestrator.status(run_id)
        if status.state == "unknown" and run_id not in self.running:
            raise KeyError(run_id)
        artifacts = [
            {"id": r.id, "block": r.block, "kind": r.artifact.kind, "uri": r.artifact.uri}
            for r in self.catalogue.by_run(run_id)
        ]
        return RunView(
            status=status,
            running=run_id in self.running,
            upload=self.uploads.get(run_id),
            artifacts=artifacts,
        )

    def events(self, run_id: str) -> Iterator[str]:
        sent = 0
        while True:
            history = self.bus.history
            while sent < len(history):
                e = history[sent]
                sent += 1
                if e.subject.startswith("run.") and e.payload.get("run_id") == run_id:
                    yield f"event: {e.subject}\ndata: {json.dumps(e.model_dump())}\n\n"
            if run_id not in self.running:
                yield "event: end\ndata: {}\n\n"
                return
            time.sleep(POLL_SECONDS)


def create_app(console: Console) -> FastAPI:
    app = FastAPI(title="EDP console API")

    @app.get("/api/blocks", response_model=list[BlockInfo])
    def blocks() -> list[BlockInfo]:
        return [
            BlockInfo(name=b.name, version=b.version, real=b.name in console.real) for b in console.blocks
        ]

    def sample_files() -> dict[str, Path]:
        files: dict[str, Path] = {}
        for folder in console.golden:
            if folder.is_dir():
                for p in sorted(folder.iterdir()):
                    if p.suffix.lower() in SAMPLE_SUFFIXES:
                        files.setdefault(p.name, p)
        return files

    @app.get("/api/samples", response_model=list[str])
    def samples() -> list[str]:
        return sorted(sample_files())

    @app.post("/api/runs/sample", response_model=StartedRun)
    def run_sample(name: str) -> StartedRun:
        path = sample_files().get(name)
        if path is None:
            raise HTTPException(status_code=404, detail=f"no sample drawing named {name!r}")
        return console.start(path.name, path.read_bytes(), data_class="synthetic")

    @app.post("/api/runs", response_model=StartedRun)
    async def run_upload(file: UploadFile) -> StartedRun:
        try:
            return console.start(file.filename or "upload", await file.read())
        except UnsupportedTypeError as exc:
            raise HTTPException(status_code=415, detail={"code": exc.code, "message": str(exc)}) from exc

    @app.get("/api/runs/{run_id}", response_model=RunView)
    def run_view(run_id: str) -> RunView:
        try:
            return console.view(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"unknown run {run_id}") from exc

    @app.get("/api/runs/{run_id}/events")
    def run_events(run_id: str) -> StreamingResponse:
        return StreamingResponse(console.events(run_id), media_type="text/event-stream")

    @app.post("/api/runs/{run_id}/review")
    def review(run_id: str, decision: ReviewDecision) -> dict[str, str]:
        if console.orchestrator.status(run_id).state != "awaiting_review":
            raise HTTPException(status_code=409, detail=f"run {run_id} is not waiting for review")
        console.review(run_id, decision)
        return {"run_id": run_id, "decision": decision.decision}

    @app.get("/api/chat", response_model=ChatStatus)
    def chat_status() -> ChatStatus:
        return console.chat_status()

    @app.post("/api/runs/{run_id}/chat", response_model=CitedAnswer)
    def chat(run_id: str, q: ChatQuestion) -> CitedAnswer:
        if not q.question.strip():
            raise HTTPException(status_code=400, detail="Ask a question first")
        if console.orchestrator.status(run_id).state == "unknown":
            raise HTTPException(status_code=404, detail=f"unknown run {run_id}")
        if not console.chat_status().available:
            raise HTTPException(status_code=503, detail=console.chat_status().reason)
        try:
            return console.ask(run_id, q)
        except GatewayError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 - provider errors: report the type, never the request
            detail = f"The model call failed ({type(exc).__name__})"
            raise HTTPException(status_code=502, detail=detail) from exc

    @app.get("/api/usage", response_model=Spend)
    def usage() -> Spend:
        if not console.chat_status().available:
            return Spend(spent_usd=0.0, calls=0)
        log = console.gateway().usage
        return Spend(spent_usd=log.spent_usd(), calls=len(log.calls()))

    @app.get("/api/artifact")
    def artifact(uri: str) -> dict:
        if not uri.startswith("fabric://cleaned/"):
            raise HTTPException(status_code=400, detail="only block outputs in the cleaned zone can be read")
        try:
            return json.loads(console.fabric.read(uri))
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    if CONSOLE_DIST.is_dir():
        app.mount("/", StaticFiles(directory=CONSOLE_DIST, html=True), name="console")
    return app


def main() -> None:
    import uvicorn

    ap = argparse.ArgumentParser(prog="python -m edp_orchestrator.server", description=__doc__)
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument(
        "--golden",
        type=Path,
        nargs="*",
        default=[],
        help="folders of sample drawings and models to offer in the console",
    )
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    uvicorn.run(create_app(Console(args.data_dir, args.golden)), host=args.host, port=args.port)


if __name__ == "__main__":
    main()

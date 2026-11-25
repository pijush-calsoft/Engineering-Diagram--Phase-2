"""Run the walking skeleton locally: upload a drawing and run it through the pipeline.

Usage: ``uv run python -m edp_orchestrator --file DRAWING --data-dir var [--run-id ID] [--real-blocks]``
"""

import argparse
import os
import uuid
from pathlib import Path

from edp_catalogue import Catalogue
from edp_contracts import Block
from edp_contracts.registry import discover_blocks
from edp_fabric import FabricStore
from edp_kit import InMemoryEventBus
from edp_orchestrator import Orchestrator, stub_blocks

parser = argparse.ArgumentParser(prog="python -m edp_orchestrator", description=__doc__)
parser.add_argument("--file", type=Path, required=True, help="drawing or model to upload")
parser.add_argument("--data-dir", type=Path, required=True, help="local data folder (git-ignored, e.g. var)")
parser.add_argument("--run-id", default=None, help="run id; a new one is made if omitted")
parser.add_argument("--real-blocks", action="store_true",
                    help="use blocks registered through the edp.blocks entry point; stubs for the rest")
args = parser.parse_args()

args.data_dir.mkdir(parents=True, exist_ok=True)
bus = InMemoryEventBus()
fabric = FabricStore(args.data_dir / "fabric", bus)
catalogue = Catalogue(args.data_dir / "catalogue.sqlite", bus)
blocks: list[Block] = list(stub_blocks())
if args.real_blocks:
    os.environ["EDP_DATA_DIR"] = str(args.data_dir)  # entry-point blocks use the same local Fabric
    real = discover_blocks()
    blocks = [real.get(b.name, b) for b in blocks]
    print("real blocks:", sorted(set(real) & {b.name for b in blocks}) or "none")
orchestrator = Orchestrator(blocks, catalogue, bus, args.data_dir / "checkpoints.sqlite")

upload = fabric.ingest(args.file.name, args.file.read_bytes(), uploader="cli")
if upload.warning:
    print(f"warning: {upload.warning}")
run_id = args.run_id or f"run-{uuid.uuid4().hex[:8]}"
status = orchestrator.start(run_id, [upload.as_artifact()])

print(f"uploaded {upload.filename} as {upload.kind}, dataset {upload.dataset_id}, commit {upload.commit}")
print(f"run {run_id}: {status.state}" + (f" ({status.error})" if status.error else ""))
for r in status.results:
    print(f"  {r['block']:<20} {r['status']}")
print("events:")
for e in bus.history:
    print(f"  {e.seq:>3} {e.subject}")
for rec in catalogue.by_run(run_id):
    if rec.artifact.kind == "report":
        locs = ", ".join(f"{s.file_id[:12]}@{s.version}" for s in rec.artifact.sources)
        print(f"report {rec.id} traces back to: {locs}")

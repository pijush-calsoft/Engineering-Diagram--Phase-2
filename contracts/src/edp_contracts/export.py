"""Write JSON Schema files for the contract and artifact models.

Usage: ``uv run python -m edp_contracts.export [OUT_DIR]`` (default ``contracts/schemas``).
"""

import json
import sys
from pathlib import Path

from pydantic import BaseModel

from edp_contracts.artifacts import ARTIFACT_MODELS
from edp_contracts.block import (
    Artifact,
    BlockContract,
    BlockRequest,
    BlockResult,
    Flag,
    SourceLocator,
)

CONTRACT_MODELS: dict[str, type[BaseModel]] = {
    "source_locator": SourceLocator,
    "artifact": Artifact,
    "flag": Flag,
    "block_request": BlockRequest,
    "block_result": BlockResult,
    "block_contract": BlockContract,
}


def all_schemas() -> dict[str, dict]:
    models = {**CONTRACT_MODELS, **ARTIFACT_MODELS}
    return {name: model.model_json_schema(mode="serialization") for name, model in models.items()}


def write_schemas(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, schema in all_schemas().items():
        path = out_dir / f"{name}.schema.json"
        path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "schemas"
    for p in write_schemas(target):
        print(p)

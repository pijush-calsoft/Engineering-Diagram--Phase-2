"""Synthetic golden-set generator (OD-7): DXF drawings with exact ground truth.

Usage: ``uv run python -m edp_eval.synth --out DIR --count N --seed S --uri-prefix s3://...``
"""

import json
from pathlib import Path

from edp_eval.golden import GoldenItem, GoldenManifest, Provenance
from edp_eval.synth.dxf_writer import generate, verify
from edp_eval.synth.parts import FAMILIES
from edp_eval.synth.profiles import PROFILES, ProfileName

PROFILE_ORDER: tuple[ProfileName, ...] = ("iso", "asme")
LABEL_FIELDS = ["dimensions", "title_block", "material", "expected_parameters"]


def write_set(out_dir: Path, count: int, seed: int, uri_prefix: str) -> GoldenManifest:
    """Write ``count`` drawings, cycling ISO/ASME and plate/bracket, plus labels and a manifest.

    ``uri_prefix`` is the Data Fabric location the files will be uploaded to
    (plan §3, ``Artifact.uri``); the files themselves are written to ``out_dir``.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = uri_prefix.rstrip("/")
    items = []
    for i in range(count):
        profile = PROFILES[PROFILE_ORDER[i % 2]]
        family = FAMILIES[(i // 2) % 2]
        doc, label = generate(profile, family, i, seed)
        dxf_path = out_dir / f"{label.id}.dxf"
        doc.saveas(dxf_path)
        (out_dir / f"{label.id}.labels.json").write_text(label.model_dump_json(indent=2), encoding="utf-8")
        errors = verify(dxf_path, label)
        if errors:
            raise AssertionError(f"{label.id}: " + "; ".join(errors))
        items.append(
            GoldenItem(
                id=label.id,
                input_format="dxf",
                part_family=family,
                provenance=Provenance(kind="internal"),
                data_uri=f"{prefix}/{label.id}.dxf",
                ground_truth_uri=f"{prefix}/{label.id}.labels.json",
                labelled=True,
                label_fields=LABEL_FIELDS,  # type: ignore[arg-type]
            )
        )
    manifest = GoldenManifest(version=f"synthetic-seed{seed}-n{count}", items=items)
    (out_dir / "manifest.json").write_text(json.dumps(manifest.model_dump(), indent=2), encoding="utf-8")
    return manifest

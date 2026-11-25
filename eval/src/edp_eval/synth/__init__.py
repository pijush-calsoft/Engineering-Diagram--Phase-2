"""Synthetic golden-set generator (OD-7): DXF drawings with exact ground truth.

Usage: ``uv run python -m edp_eval.synth --out DIR --count N --seed S --uri-prefix s3://...``
Family set for the Knowledge Graph: ``write_family_set`` (``--families N`` on the CLI).
"""

import dataclasses
import json
import random
from pathlib import Path

from edp_eval.golden import GoldenItem, GoldenManifest, Provenance
from edp_eval.synth.dxf_writer import generate, verify
from edp_eval.synth.parts import FAMILIES, Bracket, Hole, Part, Plate, sample
from edp_eval.synth.profiles import PROFILES, ProfileName

PROFILE_ORDER: tuple[ProfileName, ...] = ("iso", "asme")
LABEL_FIELDS = ["dimensions", "title_block", "material", "expected_parameters"]


def _save(out_dir: Path, doc, label) -> None:  # noqa: ANN001
    dxf_path = out_dir / f"{label.id}.dxf"
    doc.saveas(dxf_path)
    (out_dir / f"{label.id}.labels.json").write_text(label.model_dump_json(indent=2), encoding="utf-8")
    errors = verify(dxf_path, label)
    if errors:
        raise AssertionError(f"{label.id}: " + "; ".join(errors))


def _item(label_id: str, family: str, prefix: str) -> GoldenItem:
    return GoldenItem(
        id=label_id,
        input_format="dxf",
        part_family=family,
        provenance=Provenance(kind="internal"),
        data_uri=f"{prefix}/{label_id}.dxf",
        ground_truth_uri=f"{prefix}/{label_id}.labels.json",
        labelled=True,
        label_fields=LABEL_FIELDS,  # type: ignore[arg-type]
    )


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
        _save(out_dir, doc, label)
        items.append(_item(label.id, family, prefix))
    manifest = GoldenManifest(version=f"synthetic-seed{seed}-n{count}", items=items)
    (out_dir / "manifest.json").write_text(json.dumps(manifest.model_dump(), indent=2), encoding="utf-8")
    return manifest


# Standard hole sizes the generator uses (parts.sample_plate / sample_bracket).
_HOLE_SIZES = (5.5, 6.6, 9.0, 11.0)


def _revise(part: Part, step: int) -> Part:
    """Revision ``step`` of a part: 5 mm longer per step, same features (a small design change)."""
    if isinstance(part, Plate):
        inset = part.holes[0].x
        length = part.length + 5 * step
        corners = [
            (inset, inset),
            (length - inset, inset),
            (length - inset, part.width - inset),
            (inset, part.width - inset),
        ]
        holes = tuple(
            Hole(float(x), float(y), h.diameter) for (x, y), h in zip(corners, part.holes, strict=False)
        )
        return dataclasses.replace(part, length=length, holes=holes)
    assert isinstance(part, Bracket)
    return dataclasses.replace(part, flange_b=part.flange_b + 5 * step)


def _new_hole_size(part: Part) -> Part:
    """The same part with hole 1 changed to the next standard size (an adversarial revision)."""
    holes = part.holes if isinstance(part, Plate) else (part.hole,)
    current = holes[0].diameter
    bigger = next((d for d in _HOLE_SIZES if d > current), _HOLE_SIZES[0])
    changed = (dataclasses.replace(holes[0], diameter=bigger), *holes[1:])
    if isinstance(part, Plate):
        return dataclasses.replace(part, holes=changed)
    return dataclasses.replace(part, hole=changed[0])


def write_family_set(
    out_dir: Path, families: int, revisions: int, seed: int, uri_prefix: str
) -> GoldenManifest:
    """Write ``families`` x ``revisions`` drawings for the Knowledge Graph evaluation (plan Phase 3).

    - Each family is one part number with ``revisions`` revisions (A, B, C, ...), each 5 mm
      longer than the last. Parts in a family form one similar-part group.
    - The last revision of every family leaves the hole 1 diameter dimension off the drawing,
      so Interpretation reports it as a low-confidence value for corroboration.
    - In half of the families that last revision also changes hole 1 to another standard size.
      Its siblings then disagree with it, so corroboration must not resolve it. Adversarial
      families are spread over both profiles and both part types (families come in blocks of
      four: iso/asme x plate/bracket; every second block is adversarial).
    """
    if revisions < 2:
        raise ValueError("a family needs at least two revisions")
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = uri_prefix.rstrip("/")
    items = []
    for f in range(families):
        profile = PROFILES[PROFILE_ORDER[f % 2]]
        family = FAMILIES[(f // 2) % 2]
        rng = random.Random(f"{seed}-family-{f}")
        base = sample(family, rng)
        material = rng.choice(profile.materials)
        for r in range(revisions):
            part = _revise(base, r)
            last = r == revisions - 1
            if last and (f // 4) % 2 == 1:
                part = _new_hole_size(part)
            title = {"part_number": f"EDP-FAM-{f:03d}", "revision": "ABCDEFGH"[r], "material": material}
            index = f * revisions + r
            doc, label = generate(
                profile,
                family,
                index,
                seed,
                part=part,
                title=title,
                group=f"EDP-FAM-{f:03d}",
                omit=frozenset({"hole1.diameter"}) if last else frozenset(),
            )
            label = label.model_copy(update={"id": f"fam-{profile.name}-{family}-{f:03d}{'ABCDEFGH'[r]}"})
            _save(out_dir, doc, label)
            items.append(_item(label.id, family, prefix))
    manifest = GoldenManifest(version=f"family-seed{seed}-f{families}-r{revisions}", items=items)
    (out_dir / "manifest.json").write_text(json.dumps(manifest.model_dump(), indent=2), encoding="utf-8")
    return manifest

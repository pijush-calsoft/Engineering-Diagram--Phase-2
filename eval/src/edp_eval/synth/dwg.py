"""DWG copies of a synthetic DXF set, for the DWG path of the parser (plan Phase 2).

Uses LibreDWG ``dxf2dwg`` (GPLv3) as a separate process. Two faults in its DXF import are
worked around, so the DWG holds the same drawing as the DXF:

- MTEXT rotation (group code 50) inside dimension blocks is rejected (0.11 and 0.14), so the
  rotation is rewritten as the equivalent text direction vector (group code 11) first.
- LibreDWG 0.14 stores a rotated dimension's angle (DXF group code 50) as its oblique angle,
  so vertical dimensions would measure 0. When the written DWG differs from the source, it is
  dumped to JSON with ``dwgread``, the angles are set from the source DXF by entity handle,
  and the DWG is rewritten with ``dwgwrite``.

The geometry and the labels do not change; LibreDWG keeps entity handles, so the labels still apply.
"""

import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import ezdxf

from edp_eval.synth.labels import SyntheticLabel


def dxf2dwg_path(dwg2dxf: Path) -> Path:
    return dwg2dxf.with_name("dxf2dwg" + dwg2dxf.suffix)


def _run(exe: Path, args: list[str], cwd: str, timeout_s: float) -> None:
    subprocess.run([str(exe), *args], cwd=cwd, capture_output=True, timeout=timeout_s, check=False)


def _fix_dimension_angles(
    dwg_path: Path, rotations: dict[int, float], dxf2dwg: Path, timeout_s: float
) -> None:
    """Set each linear dimension's rotation from the source DXF if the DWG lost it."""
    dwgread = dxf2dwg.with_name("dwgread" + dxf2dwg.suffix)
    dwgwrite = dxf2dwg.with_name("dwgwrite" + dxf2dwg.suffix)
    if not (dwgread.is_file() and dwgwrite.is_file()):
        return
    cwd = str(dwg_path.parent)
    _run(dwgread, ["-O", "JSON", "-o", "dump.json", dwg_path.name], cwd, timeout_s)
    dump_path = dwg_path.parent / "dump.json"
    if not dump_path.is_file():
        return
    dump: dict[str, Any] = json.loads(dump_path.read_text(encoding="utf-8", errors="replace"))
    changed = False
    for obj in dump.get("OBJECTS", []):
        want = rotations.get(obj.get("handle", [0])[-1]) if obj.get("entity") == "DIMENSION_LINEAR" else None
        if want is None:
            continue
        rotation, oblique = obj.get("dim_rotation", 0.0), obj.get("oblique_angle", 0.0)
        if oblique or not math.isclose(rotation, want, abs_tol=1e-9):
            obj["dim_rotation"], obj["oblique_angle"] = want, 0.0
            changed = True
    if not changed:
        return
    dump_path.write_text(json.dumps(dump), encoding="utf-8")
    fixed = dwg_path.with_name("fixed.dwg")
    _run(dwgwrite, ["-y", "-o", fixed.name, dump_path.name], cwd, timeout_s)
    if not fixed.is_file():
        raise RuntimeError(f"dwgwrite did not rewrite {dwg_path.name}")
    shutil.move(fixed, dwg_path)


def write_dwg_set(src: Path, out: Path, dxf2dwg: Path, timeout_s: float = 120.0) -> list[str]:
    """Convert every labelled drawing in ``src`` to DWG in ``out``; copy its labels. Returns the ids."""
    out.mkdir(parents=True, exist_ok=True)
    done = []
    for label_path in sorted(src.glob("*.labels.json")):
        label = SyntheticLabel.model_validate_json(label_path.read_text(encoding="utf-8"))
        doc = ezdxf.readfile(src / f"{label.id}.dxf")
        for block in doc.blocks:
            for e in block:
                if e.dxftype() == "MTEXT" and e.dxf.hasattr("rotation"):
                    a = math.radians(e.dxf.rotation)
                    e.dxf.text_direction = (math.cos(a), math.sin(a), 0)
                    e.dxf.discard("rotation")
        rotations = {
            int(d.dxf.handle, 16): math.radians(d.dxf.get("angle", 0.0))
            for d in doc.modelspace().query("DIMENSION")
            if d.dimtype == 0  # type: ignore[attr-defined]
        }
        with tempfile.TemporaryDirectory(prefix="edp-dxf2dwg-") as tmp:
            dxf_path = Path(tmp) / f"{label.id}.dxf"
            doc.saveas(dxf_path)
            _run(dxf2dwg, ["-y", str(dxf_path)], tmp, timeout_s)
            dwg_path = dxf_path.with_suffix(".dwg")
            if not dwg_path.is_file():
                raise RuntimeError(f"dxf2dwg did not convert {label.id}")
            _fix_dimension_angles(dwg_path, rotations, dxf2dwg, timeout_s)
            shutil.copyfile(dwg_path, out / f"{label.id}.dwg")
        shutil.copyfile(label_path, out / label_path.name)
        done.append(label.id)
    return done

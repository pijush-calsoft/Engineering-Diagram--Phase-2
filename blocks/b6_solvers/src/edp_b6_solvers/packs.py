"""Domain packs: material cards and load cases as typed, versioned inputs (plan Phase 5 Solver
task 2: "material cards and load cases as typed inputs (JSON, CSV)"; deck slide 34).

A pack lives in ``domain_packs/<name>/`` at the repo root, or under ``EDP_DOMAIN_PACKS``. Each
file is identified by its SHA-256, which becomes the ``SourceLocator.file_id`` of every margin
that uses a row from it (plan Phase 5 exit criterion: every margin links to its load case row).
"""

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from edp_contracts import SourceLocator

REPO_PACKS = Path(__file__).resolve().parents[4] / "domain_packs"


class PackError(ValueError):
    pass


def packs_root() -> Path:
    env = os.environ.get("EDP_DOMAIN_PACKS", "").strip()
    return Path(env) if env else REPO_PACKS


@dataclass(frozen=True)
class PackFile:
    path: Path
    sha256: str
    data: dict[str, Any]

    def locator(self, row_id: str) -> SourceLocator:
        return SourceLocator(
            file_id=self.sha256,
            version=f"{self.path.parent.name}/{self.path.name}@{self.sha256[:12]}",
            handle=row_id,
            confidence=1.0,
        )


def load(pack: str, filename: str) -> PackFile:
    path = packs_root() / pack / filename
    if not path.is_file():
        raise PackError(f"domain pack file not found: {path}")
    raw = path.read_bytes()
    return PackFile(path=path, sha256=hashlib.sha256(raw).hexdigest(), data=json.loads(raw))


@dataclass(frozen=True)
class MaterialCard:
    grade: str
    E: float
    nu: float
    fy: float
    gamma_M0: float
    row: SourceLocator


def material(pack: PackFile, grade: str, thickness_mm: float) -> MaterialCard:
    """The card for ``grade`` with the yield strength for this nominal thickness."""
    wanted = grade.strip().upper().replace(" ", "")
    for m in pack.data["materials"]:
        if m["grade"].upper() == wanted:
            for band in m["yield_by_thickness"]:
                if thickness_mm <= band["max_thickness_mm"]:
                    return MaterialCard(
                        grade=m["grade"],
                        E=float(m["E_MPa"]),
                        nu=float(m["nu"]),
                        fy=float(band["fy_MPa"]),
                        gamma_M0=float(pack.data["gamma_M0"]),
                        row=pack.locator(f"{m['grade']}@t<={band['max_thickness_mm']}"),
                    )
            raise PackError(f"{grade}: no yield strength for thickness {thickness_mm:g} mm in the pack")
    raise PackError(
        f"material {grade!r} is not in the pack (has {[m['grade'] for m in pack.data['materials']]})"
    )

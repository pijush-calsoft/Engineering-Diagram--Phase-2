"""CalculiX connector: mesh with Gmsh, write the input deck, run ``ccx``, read the results.

Both tools are GPL and run only as separate processes (plan §9; OD-21: no containers). They are
found through settings, like LibreDWG for DWG input (setup guide §2):

- ``EDP_CCX``: the ``ccx`` executable, or ``tools/conda-fem`` (conda-forge ``calculix``).
- ``EDP_GMSH_PYTHON``: a Python that has the ``gmsh`` wheel, or ``tools/gmsh-venv``.

Elements are second-order tetrahedra (C3D10). Stresses are read from the ``.dat`` file at the
integration points and turned into von Mises stress; displacements are read at the nodes.
"""

import json
import math
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_TOOLS = Path(__file__).resolve().parents[4] / "tools"
MESHER = Path(__file__).with_name("gmsh_mesh.py")


class SolverUnavailableError(RuntimeError):
    code = "SOLVER_UNAVAILABLE"


def _first(*paths: Path) -> Path | None:
    return next((p for p in paths if p.is_file()), None)


def ccx_path() -> Path | None:
    env = os.environ.get("EDP_CCX", "").strip()
    if env:
        return Path(env) if Path(env).is_file() else None
    return _first(
        REPO_TOOLS / "conda-fem" / "Library" / "bin" / "ccx.exe", REPO_TOOLS / "conda-fem" / "bin" / "ccx"
    )


def gmsh_python() -> Path | None:
    env = os.environ.get("EDP_GMSH_PYTHON", "").strip()
    if env:
        return Path(env) if Path(env).is_file() else None
    return _first(
        REPO_TOOLS / "gmsh-venv" / "Scripts" / "python.exe", REPO_TOOLS / "gmsh-venv" / "bin" / "python"
    )


def _ccx_env(ccx: Path) -> dict[str, str]:
    """PATH with the conda environment's DLL folders, so ccx finds its runtime libraries."""
    env = dict(os.environ)
    bin_dir = ccx.parent
    extra = [bin_dir, bin_dir.parent / "mingw-w64" / "bin", bin_dir.parent.parent]
    env["PATH"] = os.pathsep.join([str(p) for p in extra] + [env.get("PATH", "")])
    return env


@dataclass
class Mesh:
    nodes: dict[int, tuple[float, float, float]]
    elements: list[list[int]]
    sets: dict[str, list[int]]
    quality: dict[str, Any]


@dataclass
class Results:
    max_von_mises: float
    max_element: int
    max_point: tuple[float, float, float]
    max_displacement: float
    max_displacement_node: int
    log_tail: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def mesh_step(step_file: Path, size_max: float, size_min: float, timeout: float) -> Mesh:
    py = gmsh_python()
    if py is None:
        raise SolverUnavailableError("Gmsh not found: set EDP_GMSH_PYTHON to a Python with the gmsh wheel")
    with tempfile.TemporaryDirectory(prefix="edp-mesh-") as tmp:
        job = Path(tmp) / "job.json"
        out = Path(tmp) / "mesh.json"
        job.write_text(
            json.dumps({"step": str(step_file), "out": str(out), "size_max": size_max, "size_min": size_min}),
            encoding="utf-8",
        )
        proc = subprocess.run(
            [str(py), "-I", str(MESHER), str(job)],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if proc.returncode != 0 or not out.exists():
            raise RuntimeError(f"Gmsh failed: {(proc.stderr or proc.stdout)[-500:]}")
        data = json.loads(out.read_text(encoding="utf-8"))
    return Mesh(
        nodes={int(k): (v[0], v[1], v[2]) for k, v in data["nodes"].items()},
        elements=data["elements"],
        sets=data["sets"],
        quality=data["quality"],
    )


def write_inp(
    mesh: Mesh,
    E: float,
    nu: float,
    fixed: list[int],
    loads: dict[int, tuple[float, float, float]],
) -> str:
    """A linear static CalculiX deck: units mm, N, MPa."""
    out = ["*HEADING", "EDP block 6 linear static run", "*NODE, NSET=NALL"]
    out += [f"{n}, {x:.9g}, {y:.9g}, {z:.9g}" for n, (x, y, z) in sorted(mesh.nodes.items())]
    out.append("*ELEMENT, TYPE=C3D10, ELSET=EALL")
    out += [", ".join(str(v) for v in e) for e in mesh.elements]
    out.append("*NSET, NSET=NFIX")
    out += _rows(fixed)
    out += [
        "*MATERIAL, NAME=STEEL",
        "*ELASTIC",
        f"{E:.9g}, {nu:.9g}",
        "*SOLID SECTION, ELSET=EALL, MATERIAL=STEEL",
    ]
    out += ["*STEP", "*STATIC", "*BOUNDARY", "NFIX, 1, 3, 0.0", "*CLOAD"]
    for n, (fx, fy, fz) in sorted(loads.items()):
        for dof, f in ((1, fx), (2, fy), (3, fz)):
            if f:
                out.append(f"{n}, {dof}, {f:.9g}")
    out += ["*NODE PRINT, NSET=NALL", "U", "*EL PRINT, ELSET=EALL", "S", "*END STEP"]
    return "\n".join(out) + "\n"


def _rows(ids: list[int], per_line: int = 12) -> list[str]:
    return [", ".join(str(i) for i in ids[k : k + per_line]) for k in range(0, len(ids), per_line)]


def von_mises(s: list[float]) -> float:
    sxx, syy, szz, sxy, sxz, syz = s
    return math.sqrt(
        0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2) + 3 * (sxy**2 + sxz**2 + syz**2)
    )


def parse_dat(text: str) -> tuple[dict[int, float], dict[int, float]]:
    """Per-node displacement magnitude and per-element maximum von Mises stress from a ``.dat`` file."""
    disp: dict[int, float] = {}
    stress: dict[int, float] = {}
    mode = None
    for line in text.splitlines():
        low = line.strip().lower()
        if low.startswith("displacements"):
            mode = "u"
            continue
        if low.startswith("stresses"):
            mode = "s"
            continue
        parts = line.split()
        if not parts or mode is None:
            continue
        try:
            nums = [float(p) for p in parts]
        except ValueError:
            mode = None
            continue
        if mode == "u" and len(nums) == 4:
            disp[int(nums[0])] = math.sqrt(nums[1] ** 2 + nums[2] ** 2 + nums[3] ** 2)
        elif mode == "s" and len(nums) == 8:
            e = int(nums[0])
            stress[e] = max(stress.get(e, 0.0), von_mises(nums[2:8]))
    return disp, stress


def run_ccx(deck: str, mesh: Mesh, timeout: float) -> Results:
    ccx = ccx_path()
    if ccx is None:
        raise SolverUnavailableError("CalculiX not found: set EDP_CCX to the ccx executable")
    with tempfile.TemporaryDirectory(prefix="edp-ccx-") as tmp:
        work = Path(tmp)
        (work / "job.inp").write_text(deck, encoding="utf-8")
        proc = subprocess.run(
            [str(ccx), "-i", "job"],
            cwd=work,
            env=_ccx_env(ccx),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        dat = work / "job.dat"
        if proc.returncode != 0 or not dat.exists():
            raise RuntimeError(f"CalculiX failed: {(proc.stdout + proc.stderr)[-800:]}")
        disp, stress = parse_dat(dat.read_text(encoding="utf-8", errors="replace"))
        tail = proc.stdout[-400:]
        version = next(
            (ln.split("Version", 1)[1].strip() for ln in proc.stdout.splitlines() if "This is Version" in ln),
            None,
        )
    if not stress or not disp:
        raise RuntimeError("CalculiX wrote no stresses or displacements")
    e_max = max(stress, key=lambda e: stress[e])
    n_max = max(disp, key=lambda n: disp[n])
    element = next(e for e in mesh.elements if e[0] == e_max)
    corners = [mesh.nodes[n] for n in element[1:5]]
    point = tuple(sum(c[i] for c in corners) / 4 for i in range(3))
    return Results(
        max_von_mises=stress[e_max],
        max_element=e_max,
        max_point=(point[0], point[1], point[2]),
        max_displacement=disp[n_max],
        max_displacement_node=n_max,
        log_tail=tail,
        extra={"version": version},
    )

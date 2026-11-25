"""DWG input: LibreDWG ``dwg2dxf`` as an isolated CLI, then the DXF path (plan Phase 2, "Approach by input").

LibreDWG is GPLv3, so it only ever runs as a separate process, never imported (plan §9).
Each conversion runs in its own temporary folder, without a shell, with a time limit.
Converter warning and error lines become ``DWG_CONVERSION`` info flags: "log conversion
warnings as flags" (plan Phase 2). A conversion that writes no DXF is a blocking failure.

The converter is found from ``EDP_DWG2DXF`` (path to ``dwg2dxf``), else in the local
``tools/`` installs, newest first (LibreDWG 0.14 release build, then 0.11 from conda-forge;
OD-49), else on ``PATH``. The time limit is ``EDP_DWG2DXF_TIMEOUT`` seconds;
the default of 120 s is a starting value, not a plan value (OD-48).
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from edp_contracts import Flag

DEFAULT_TIMEOUT_S = 120.0
_TOOLS = Path(__file__).resolve().parents[4] / "tools"
_LOCAL = (
    _TOOLS / "libredwg-0.14-win64" / "dwg2dxf.exe",
    _TOOLS / "conda-libredwg" / "Library" / "bin" / "dwg2dxf.exe",
)
MAX_FLAGGED_LINES = 20


class DwgConversionError(RuntimeError):
    pass


def converter() -> Path | None:
    configured = os.environ.get("EDP_DWG2DXF")
    if configured:
        return Path(configured)
    for local in _LOCAL:
        if local.is_file():
            return local
    found = shutil.which("dwg2dxf")
    return Path(found) if found else None


def convert(data: bytes) -> tuple[bytes, list[Flag]]:
    """DWG bytes to DXF bytes, plus the converter's messages as info flags."""
    exe = converter()
    if exe is None or not exe.is_file():
        raise DwgConversionError("dwg2dxf not found: install LibreDWG and set EDP_DWG2DXF (see docs)")
    timeout = float(os.environ.get("EDP_DWG2DXF_TIMEOUT", DEFAULT_TIMEOUT_S))
    with tempfile.TemporaryDirectory(prefix="edp-dwg-") as tmp:
        src, out = Path(tmp) / "input.dwg", Path(tmp) / "output.dxf"
        src.write_bytes(data)
        try:
            proc = subprocess.run(
                [str(exe), "-y", "-o", str(out), str(src)],
                cwd=tmp,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise DwgConversionError(f"dwg2dxf did not finish within {timeout:g} s") from exc
        messages = (proc.stdout + proc.stderr).decode("utf-8", errors="replace").splitlines()
        if not out.is_file() or out.stat().st_size == 0:
            detail = "; ".join(m for m in messages if m.strip())[:400]
            raise DwgConversionError(f"dwg2dxf produced no DXF (exit {proc.returncode}): {detail}")
        notes = [m.strip() for m in messages if "warning" in m.lower() or "error" in m.lower()]
        flags = [
            Flag(code="DWG_CONVERSION", severity="info", message=f"dwg2dxf: {m}")
            for m in notes[:MAX_FLAGGED_LINES]
        ]
        if len(notes) > MAX_FLAGGED_LINES:
            flags.append(
                Flag(
                    code="DWG_CONVERSION",
                    severity="info",
                    message=f"dwg2dxf: {len(notes) - MAX_FLAGGED_LINES} more message(s) not shown",
                )
            )
        return out.read_bytes(), flags

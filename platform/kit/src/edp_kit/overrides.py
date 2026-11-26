"""Design overrides: a person changes a dimension and re-runs (added 2026-11-26).

The deck's loop runs from the drawing to an editable model and back: an engineer changes a
value, the model, simulation and report follow, and the change is marked on the drawing for
revision (deck slides 10 and 85). A run carries such changes in its parameters,
``{"overrides": {"thickness": 25.0}}``, in millimetres.

Blocks 4, 6 and 8 read them through ``overrides`` so they agree on what changed. The drawing
and its design graph are never edited: the design graph keeps what the drawing says, and every
block that uses an overridden value says so.

Only the plate thickness can be overridden for now: it is the design variable of a base plate,
and changing it keeps the holes and the load footprint valid. Others wait for the redline step.
"""

import math
from typing import Any

from edp_contracts import BlockRequest

OVERRIDABLE = ("thickness",)


class OverrideError(ValueError):
    """The run's overrides name an unknown parameter or hold a value that is not a size."""


def parse_overrides(raw: Any) -> dict[str, float]:
    """Validated overrides from a run parameter value; ``OverrideError`` when invalid."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise OverrideError("overrides must map parameter names to values in mm")
    out: dict[str, float] = {}
    for name, value in raw.items():
        if name not in OVERRIDABLE:
            raise OverrideError(f"{name!r} cannot be overridden (allowed: {', '.join(OVERRIDABLE)})")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise OverrideError(f"{name}: {value!r} is not a number")
        if not math.isfinite(value) or value <= 0:
            raise OverrideError(f"{name}: {value!r} must be a positive size in mm")
        out[str(name)] = float(value)
    return out


def overrides(req: BlockRequest) -> dict[str, float]:
    """The run's overrides; ``OverrideError`` when invalid."""
    return parse_overrides(req.params.get("overrides"))

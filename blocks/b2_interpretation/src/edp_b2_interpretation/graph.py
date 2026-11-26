"""Build the design graph and run unit checks (plan Phase 3, Interpretation tasks 1, 4, 5).

Units are normalised with pint (plan §4.2 block 2, Phase 3 task 4). Every
parameter keeps its drawing value and unit and gets ``value_mm``. Contradictions
and missing units become flags; low-confidence flags carry a reason code in
brackets, e.g. ``[UNDIMENSIONED]`` (Phase 3 task 5).

Requirements (Phase 3 task 3) are not parsed yet: they need the LLM path (OD-43).
"""

from typing import Any

import pint

from edp_b2_interpretation.recognise import Param, Recognition, recognise
from edp_contracts import Flag
from edp_contracts.artifacts.design_graph import DesignEdge, DesignGraph, DesignNode
from edp_contracts.artifacts.geometry import Geometry

_UREG = pint.UnitRegistry()
_PINT_NAMES = {"mm": "millimeter", "cm": "centimeter", "m": "meter", "in": "inch", "ft": "foot"}


def to_mm(value: float, unit: str | None) -> float | None:
    if unit not in _PINT_NAMES:
        return None
    return float(_UREG.Quantity(value, _PINT_NAMES[unit]).to("millimeter").magnitude)


def _param_attrs(p: Param, unit: str | None) -> dict[str, Any]:
    return {
        "name": p.name,
        "value": p.value,
        "unit": unit,
        "value_mm": to_mm(p.value, unit),
        "association": p.association,
        "confidence": p.confidence,
        "dimensions": p.dimension_handles,
    }


def interpret(geometry: Geometry) -> tuple[DesignGraph, list[Flag], dict[str, Any]]:
    rec: Recognition = recognise(geometry)
    flags = list(rec.flags)
    unit = geometry.units
    if unit is None:
        flags.append(
            Flag(code="UNIT_MISMATCH", message="[UNITS_UNKNOWN] drawing has no units; values not normalised")
        )
    nodes: list[DesignNode] = []
    edges: list[DesignEdge] = []
    counters: dict[str, int] = {}
    order = sorted(rec.features, key=lambda f: (f.type, f.sources[0].bbox or (0, 0, 0, 0)))
    for f in order:
        counters[f.type] = counters.get(f.type, 0) + 1
        fid = f"{f.type}{counters[f.type]}"
        nodes.append(DesignNode(id=fid, kind="feature", feature_type=f.type, sources=f.sources))
        for p in f.params.values():
            pid = f"{fid}.{p.name}"
            locs = [s.model_copy(update={"confidence": p.confidence}) for s in p.sources]
            nodes.append(DesignNode(id=pid, kind="parameter", attributes=_param_attrs(p, unit), sources=locs))
            edges.append(DesignEdge(source=fid, target=pid, relation="has_parameter"))
    for d in rec.unassociated:
        attrs = {
            "name": d.data.get("dimtype"),
            "value": d.data["value"],
            "unit": unit,
            "value_mm": to_mm(d.data["value"], unit),
            "association": "part_level",
            "dimensions": [d.locator.handle],
        }
        role = rec.outline_roles.get(d.locator.handle or "")
        if role:
            attrs["role"] = role  # outline size: length, width or thickness (used by block 4)
        nodes.append(
            DesignNode(id=f"dim.{d.locator.handle}", kind="parameter", attributes=attrs, sources=[d.locator])
        )
    tb = geometry.title_block
    if tb and tb.material and tb.material.value:
        nodes.append(
            DesignNode(
                id="material",
                kind="material",
                attributes={"name": tb.material.value},
                sources=[tb.material.locator],
            )
        )
    if tb and tb.tolerances and tb.tolerances.value:
        nodes.append(
            DesignNode(
                id="general_tolerance",
                kind="tolerance",
                attributes={"text": tb.tolerances.value},
                sources=[tb.tolerances.locator],
            )
        )
    if not any(n.kind in ("feature", "parameter") for n in nodes):
        # OD-62: nothing to model. Say so rather than hand an empty graph on as a result.
        # 3D models are not interpreted yet (rules read 2D drawings), so for them an empty
        # graph is expected: noted, not stopped. Block 1 flags a 3D file with no solid.
        flags.append(
            Flag(
                code="EMPTY_INTERPRETATION",
                severity="info" if geometry.solids else "review",
                message=(
                    f"3D model with {len(geometry.solids)} solid(s): block 2 interprets 2D drawings only"
                    if geometry.solids
                    else f"no feature or dimension recognised from {len(geometry.entities)} entities"
                ),
            )
        )
    metrics = {
        "features": {t: n for t, n in counters.items()},
        "part_level_dimensions": len(rec.unassociated),
        "flags": len(flags),
    }
    return DesignGraph(nodes=nodes, edges=edges), flags, metrics

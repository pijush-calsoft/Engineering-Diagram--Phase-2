"""Template library for block 4 (plan Phase 4 Generation task 1: template first, LLM second;
deck slide 47: "Template zoo: versioned part templates in Git").

A template turns a design graph into an editable CadQuery script. The script starts with a
named-parameter block, one line per parameter, and every parameter traces to the design-graph
node it came from, so each value carries the drawing's source locator (plan principle 1;
Phase 4 exit criterion: parameters with source locators 100 %).

Template ``plate`` covers flat plates with through holes and an optional slot: the generic
``plate`` family and the construction ``base_plate`` family. Its geometry is built in model
millimetres: x along the length, y along the width, z through the thickness, origin at the
plan view's bottom-left corner (the datum the drawing dimensions hole positions from).
"""

from dataclasses import dataclass, field

from edp_contracts import SourceLocator
from edp_contracts.artifacts.design_graph import DesignGraph, DesignNode

TEMPLATE_VERSION = "plate-0.1.0"


class NoTemplateError(ValueError):
    """The design graph does not match any template (the LLM path is not built yet)."""


@dataclass
class Param:
    name: str
    value: float
    source: SourceLocator
    comment: str


@dataclass
class Plan:
    template: str
    params: list[Param] = field(default_factory=list)
    holes: list[tuple[str, str, str]] = field(default_factory=list)  # parameter names: x, y, diameter
    slot: tuple[str, str] | None = None  # parameter names: length, width


def _mm(node: DesignNode) -> float:
    value = node.attributes.get("value_mm")
    if value is None:
        raise NoTemplateError(f"{node.id}: value has no millimetre conversion (units unknown)")
    return float(value)


def _source(node: DesignNode) -> SourceLocator:
    if not node.sources:
        raise NoTemplateError(f"{node.id}: parameter has no source locator")
    return node.sources[0]


def plan_plate(graph: DesignGraph) -> Plan:
    """Match the ``plate`` template, or raise ``NoTemplateError`` with the reason."""
    nodes = {n.id: n for n in graph.nodes}
    if any(n.kind == "feature" and n.feature_type == "bend" for n in graph.nodes):
        raise NoTemplateError("the part has a bend; no sheet-metal template yet")
    outline: dict[str, DesignNode] = {}
    for n in graph.nodes:
        role = n.attributes.get("role")
        if n.kind == "parameter" and role in ("length", "width", "thickness"):
            outline.setdefault(role, n)
    missing = sorted({"length", "width", "thickness"} - set(outline))
    if missing:
        raise NoTemplateError(f"outline size not found on the drawing: {', '.join(missing)}")
    plan = Plan(template="plate")
    for role in ("length", "width", "thickness"):
        n = outline[role]
        plan.params.append(Param(role, _mm(n), _source(n), f"plate {role}, from {n.id}"))

    children: dict[str, dict[str, DesignNode]] = {}
    for e in graph.edges:
        if e.relation == "has_parameter":
            child = nodes[e.target]
            children.setdefault(e.source, {})[str(child.attributes.get("name"))] = child
    holes = sorted(
        (n for n in graph.nodes if n.kind == "feature" and n.feature_type == "hole"), key=lambda n: n.id
    )
    for h in holes:
        kids = children.get(h.id, {})
        if not {"diameter", "x", "y"} <= set(kids):
            raise NoTemplateError(f"{h.id}: needs diameter, x and y (has {sorted(kids)})")
        names = []
        for key in ("x", "y", "diameter"):
            name = f"{h.id}_{key}"
            node = kids[key]
            plan.params.append(Param(name, _mm(node), _source(node), f"{h.id} {key}, from {node.id}"))
            names.append(name)
        plan.holes.append((names[0], names[1], names[2]))
    slots = [n for n in graph.nodes if n.kind == "feature" and n.feature_type == "slot"]
    if len(slots) > 1:
        raise NoTemplateError("more than one slot; the plate template has one centred slot")
    if slots:
        kids = children.get(slots[0].id, {})
        if not {"length", "width"} <= set(kids):
            raise NoTemplateError(f"{slots[0].id}: needs length and width")
        for key in ("length", "width"):
            plan.params.append(
                Param(f"slot_{key}", _mm(kids[key]), _source(kids[key]), f"slot {key}, from {kids[key].id}")
            )
        plan.slot = ("slot_length", "slot_width")
    return plan


def render_plate(plan: Plan, header: str) -> str:
    """The CadQuery source for a ``plate`` plan. Editing a parameter line changes the model."""
    lines = [f'"""{header}"""', "import cadquery as cq", ""]
    lines.append(
        "# --- parameters (mm); each one traces to a drawing dimension (see the parameter table) ---"
    )
    for p in plan.params:
        lines.append(f"{p.name} = {p.value!r}  # {p.comment}")
    lines += [
        "",
        "# --- model: x along the length, y along the width, origin at the plan view's datum corner ---",
        "result = cq.Workplane('XY').box(length, width, thickness, centered=False)",
    ]
    for x, y, d in plan.holes:
        lines.append(
            f"result = result.cut(cq.Workplane('XY').center({x}, {y}).circle({d} / 2)"
            ".extrude(thickness + 2).translate((0, 0, -1)))"
        )
    if plan.slot:
        sl, sw = plan.slot
        lines.append(
            f"result = result.cut(cq.Workplane('XY').center(length / 2, width / 2).slot2D({sl}, {sw})"
            ".extrude(thickness + 2).translate((0, 0, -1)))"
        )
    return "\n".join(lines) + "\n"

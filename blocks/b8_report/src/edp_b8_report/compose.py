"""Compose the descriptive and diagnostic insight report (plan Phase 6 Insight tasks 1 and 2;
deck slide 56, levels "Descriptive: what happened" and "Diagnostic: why", Release 1).

Text comes from fixed templates. Every number is inserted by code from a claim, and every claim
points into the Run Store (``factcheck.RunStore``). No language model writes any of it yet: the
narrative writer through the Model Gateway (deck slide 40 stage 3) is a later step.
"""

import math
import re
from dataclasses import dataclass, field
from typing import Any

from edp_b8_report.factcheck import RunStore, claim, fmt
from edp_contracts.artifacts.report import NumericClaim, Report, ReportSection, SectionKey

PLACEHOLDER = re.compile(r"\{([A-Za-z0-9_.]+)\}")


@dataclass
class Builder:
    store: RunStore
    claims: dict[str, NumericClaim] = field(default_factory=dict)
    identifiers: list[str] = field(default_factory=list)
    sections: list[ReportSection] = field(default_factory=list)

    def add(self, cid: str, ref: str, unit: str | None = None) -> None:
        self.claims[cid] = claim(cid, ref, self.store, unit)

    def ident(self, *values: object) -> None:
        self.identifiers.extend(str(v) for v in values if v is not None and str(v))

    def section(self, key: SectionKey, template: str) -> None:
        cited: list[str] = []

        def put(m: re.Match[str]) -> str:
            cid = m.group(1)
            cited.append(cid)
            return fmt(self.claims[cid].value)

        text = PLACEHOLDER.sub(put, template)
        self.sections.append(ReportSection(key=key, text=text, claim_ids=sorted(set(cited))))


def _pointer(nodes: list[dict[str, Any]], node_id: str) -> int:
    return next(i for i, n in enumerate(nodes) if n["id"] == node_id)


def compose(run_id: str, store: RunStore) -> tuple[Report, list[str], dict[str, Any]]:
    """The report, the identifiers the fact checker must ignore, and a summary for the document."""
    b = Builder(store)
    graph = store.documents["design_graph"]
    nodes = graph["nodes"]
    runs = store.documents["solver_runs"]
    title = store.documents.get("title_block", {})
    part = (title.get("part_number") or {}).get("value") or "unidentified part"
    revision = (title.get("revision") or {}).get("value") or "-"
    b.ident(part, revision)

    for role in ("length", "width", "thickness"):
        i = next(i for i, n in enumerate(nodes) if n["attributes"].get("role") == role)
        b.add(f"plate.{role}", f"design_graph:/nodes/{i}/attributes/value_mm", "mm")
    holes = sorted(n["id"] for n in nodes if n["kind"] == "feature" and n.get("feature_type") == "hole")
    b.ident(*holes)
    if holes:
        b.add(
            "hole.diameter",
            f"design_graph:/nodes/{_pointer(nodes, holes[0] + '.diameter')}/attributes/value_mm",
            "mm",
        )

    mesh = "solver_runs:/mesh"
    b.add("mesh.elements", f"{mesh}/elements")
    b.add("mesh.size_max", f"{mesh}/size_max_mm", "mm")
    b.add("mesh.size_min", f"{mesh}/size_min_mm", "mm")
    b.add("mesh.jacobian", f"{mesh}/min_scaled_jacobian")

    run0 = runs["runs"][0]
    mat = run0["material"]
    b.ident(mat["grade"], mat["row"]["handle"], runs["domain_pack"], "C3D10", "gamma_M0", "f_y", "OD-56")
    b.add("mat.fy", "solver_runs:/runs/0/material/fy_MPa", "MPa")
    b.add("mat.gamma", "solver_runs:/runs/0/material/gamma_M0")
    b.add("mat.E", "solver_runs:/runs/0/material/E_MPa", "MPa")

    lc_doc = store.documents["load_cases"]["load_cases"]
    margin_lines: list[str] = []
    governing: list[dict[str, Any]] = []
    for k, r in enumerate(runs["runs"]):
        lc_index = next(i for i, lc in enumerate(lc_doc) if lc["id"] == r["load_case_id"])
        b.ident(r["load_case_id"], r["solver_run_id"], lc_doc[lc_index].get("column_section"))
        p = f"lc{k}"
        b.add(f"{p}.force", f"solver_runs:/runs/{k}/total_force_N", "N")
        b.add(f"{p}.bx", f"load_cases:/load_cases/{lc_index}/column_footprint_mm/0", "mm")
        b.add(f"{p}.by", f"load_cases:/load_cases/{lc_index}/column_footprint_mm/1", "mm")
        b.add(f"{p}.allow", f"margins:/margins/{k}/allowable", "MPa")
        b.add(f"{p}.stress", f"margins:/margins/{k}/computed", "MPa")
        b.add(f"{p}.margin", f"margins:/margins/{k}/margin")
        b.add(f"{p}.disp", f"solver_runs:/runs/{k}/max_displacement_mm", "mm")
        for axis, name in enumerate("xyz"):
            b.add(f"{p}.{name}", f"solver_runs:/runs/{k}/max_point_mm/{axis}", "mm")
        where = store.documents["margins"]["margins"][k]["governing_location"]["handle"]
        b.ident(where)
        near = _nearest_hole(nodes, holes, r["max_point_mm"])
        verdict = (
            "below one: the plate does not carry this load as modelled"
            if b.claims[f"{p}.margin"].value < 1
            else "at or above one"
        )
        margin_lines.append(
            f"Load case {r['load_case_id']}: allowable stress {{{p}.allow}} MPa (f_y / gamma_M0); "
            f"peak von Mises stress {{{p}.stress}} MPa at x {{{p}.x}}, y {{{p}.y}}, z {{{p}.z}} mm "
            f"({where}); margin {{{p}.margin}}, {verdict}. Maximum displacement {{{p}.disp}} mm."
            + (f" The anchor hole nearest the peak is {near}." if near else "")
        )
        governing.append(
            {"load_case": r["load_case_id"], "nearest": near, "illustrative": r["illustrative_load"]}
        )

    first = runs["runs"][0]
    illustrative = any(r["illustrative_load"] for r in runs["runs"])
    b.section(
        "summary",
        f"Column base plate {part}, revision {revision}, steel {mat['grade']}. "
        f"Under load case {first['load_case_id']} the peak von Mises stress is {{lc0.stress}} MPa against an "
        f"allowable of {{lc0.allow}} MPa, a margin of {{lc0.margin}}"
        + (" (below one)." if b.claims["lc0.margin"].value < 1 else ".")
        + (" The load is illustrative, not a design value (OD-56)." if illustrative else ""),
    )
    hole_text = (
        f" Anchor holes {', '.join(holes)}, diameter {{hole.diameter}} mm."
        if holes
        else " No holes were read."
    )
    b.section(
        "inputs",
        "Plate {plate.length} x {plate.width} x {plate.thickness} mm, read from the drawing's dimensions."
        + hole_text
        + f" Material {mat['grade']} from domain pack {runs['domain_pack']}: f_y {{mat.fy}} MPa for this "
        f"thickness ({mat['row']['handle']}), gamma_M0 {{mat.gamma}}, E {{mat.E}} MPa. "
        + " ".join(
            f"Load case {r['load_case_id']}: tension {{lc{k}.force}} N over a {{lc{k}.bx}} x {{lc{k}.by}} mm "
            "column footprint centred on the plate."
            for k, r in enumerate(runs["runs"])
        ),
    )
    b.section(
        "model",
        "Editable CadQuery script generated from the design graph by template; every script parameter traces "
        "to a drawing dimension. Meshed with Gmsh into {mesh.elements} second-order tetrahedra (C3D10), "
        "element size {mesh.size_max} mm down to {mesh.size_min} mm, "
        "minimum scaled Jacobian {mesh.jacobian}. "
        "Solved with CalculiX, linear static.",
    )
    b.section("margins", " ".join(margin_lines))
    b.section("envelope", "Not computed: the surrogate and failure-envelope block is not built yet.")
    flag_text = []
    if illustrative:
        flag_text.append("The load case is illustrative and must be replaced with project loads (OD-56).")
    if any(b.claims[f"lc{k}.margin"].value < 1 for k in range(len(runs["runs"]))):
        flag_text.append("At least one margin is below one.")
    flag_text.append(
        "A peak at a fixed bore edge is mesh-sensitive, and no mesh convergence study has been run yet."
    )
    b.section("flags", " ".join(flag_text))
    b.section(
        "assumptions",
        " ".join(a[0].upper() + a[1:] + "." for a in first["assumptions"])
        + " The report text comes from a fixed template; no language model wrote it.",
    )
    report = Report(run_id=run_id, format="docx", sections=b.sections, claims=list(b.claims.values()))
    summary = {"part": part, "revision": revision, "grade": mat["grade"], "governing": governing}
    return report, b.identifiers, summary


def _nearest_hole(nodes: list[dict[str, Any]], holes: list[str], point: list[float]) -> str | None:
    best, best_d = None, math.inf
    values = {n["id"]: n["attributes"].get("value_mm") for n in nodes}
    for h in holes:
        x, y = values.get(f"{h}.x"), values.get(f"{h}.y")
        if x is None or y is None:
            continue
        d = math.hypot(point[0] - x, point[1] - y)
        if d < best_d:
            best, best_d = h, d
    return best

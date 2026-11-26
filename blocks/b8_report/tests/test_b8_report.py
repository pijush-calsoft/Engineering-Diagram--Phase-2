import copy

from edp_b8_report import RunStore, check, compose, fmt


def documents() -> dict:
    loc = {"file_id": "f", "version": "v", "handle": "x", "confidence": 1.0}
    nodes = [
        {"id": "dim.A", "kind": "parameter", "attributes": {"role": "length", "value_mm": 300.0}},
        {"id": "dim.B", "kind": "parameter", "attributes": {"role": "width", "value_mm": 250.0}},
        {"id": "dim.C", "kind": "parameter", "attributes": {"role": "thickness", "value_mm": 20.0}},
        {"id": "hole1", "kind": "feature", "feature_type": "hole", "attributes": {}},
        {"id": "hole1.diameter", "kind": "parameter", "attributes": {"value_mm": 22.0}},
        {"id": "hole1.x", "kind": "parameter", "attributes": {"value_mm": 60.0}},
        {"id": "hole1.y", "kind": "parameter", "attributes": {"value_mm": 60.0}},
    ]
    run = {
        "solver_run_id": "ccx-1",
        "solver": "calculix",
        "load_case_id": "LC-1",
        "load_case_row": loc,
        "illustrative_load": True,
        "model_version": "m",
        "material": {
            "grade": "S355JR",
            "fy_MPa": 345.0,
            "gamma_M0": 1.0,
            "E_MPa": 210000.0,
            "nu": 0.3,
            "row": {**loc, "handle": "S355JR@t<=40"},
        },
        "total_force_N": 50000.0,
        "fixed_nodes": 10,
        "loaded_nodes": 20,
        "max_von_mises_MPa": 172.5,
        "max_point_mm": [70.0, 61.0, 0.5],
        "max_displacement_mm": 0.42,
        "allowable_MPa": 345.0,
        "seconds": 1.0,
        "assumptions": ["linear elastic"],
    }
    return {
        "design_graph": {"nodes": nodes, "edges": []},
        "solver_runs": {
            "domain_pack": "construction",
            "materials_sha256": "a" * 64,
            "load_cases_sha256": "b" * 64,
            "mesh": {
                "elements": 1200,
                "nodes": 2500,
                "element_type": "C3D10",
                "size_max_mm": 10.0,
                "size_min_mm": 2.5,
                "min_scaled_jacobian": 0.61,
            },
            "runs": [run],
        },
        "margins": {
            "margins": [
                {
                    "load_case_id": "LC-1",
                    "allowable": 345.0,
                    "computed": 172.5,
                    "margin": 2.0,
                    "governing_location": {**loc, "handle": "element 9"},
                }
            ]
        },
        "load_cases": {
            "load_cases": [{"id": "LC-1", "column_footprint_mm": [200, 190], "column_section": "HEA 200"}]
        },
        "title_block": {"part_number": {"value": "EDP-BP-0001"}, "revision": {"value": "A"}},
    }


def test_fmt_prints_three_significant_figures():
    assert [fmt(v) for v in (986.25, 0.35994, 7.5, 1.875, 34893, 1.0)] == [
        "986",
        "0.36",
        "7.5",
        "1.88",
        "34893",
        "1",
    ]


def test_composed_report_passes_the_fact_check():
    store = RunStore(documents())
    report, identifiers, summary = compose("run-1", store)
    assert check(report, store, identifiers) == []
    assert {s.key for s in report.sections} == {
        "summary",
        "inputs",
        "model",
        "margins",
        "envelope",
        "flags",
        "assumptions",
    }
    assert summary["governing"][0]["nearest"] == "hole1"
    margins = next(s for s in report.sections if s.key == "margins")
    assert "margin 2," in margins.text and "lc0.margin" in margins.claim_ids


def test_a_changed_run_store_value_blocks_the_report():
    docs = documents()
    report, identifiers, _ = compose("run-1", RunStore(docs))
    changed = copy.deepcopy(docs)
    changed["margins"]["margins"][0]["computed"] = 180.0
    problems = check(report, RunStore(changed), identifiers)
    assert any("lc0.stress" in p for p in problems)


def test_a_typed_number_blocks_the_report():
    store = RunStore(documents())
    report, identifiers, _ = compose("run-1", store)
    report.sections[0].text += " The bolts are 24 mm."
    problems = check(report, store, identifiers)
    assert problems == ["section summary: number 24 is not a cited Run Store value"]

import random

import pytest

from edp_b1_parser import dxf
from edp_b2_interpretation import interpret
from edp_eval.synth.construction import (
    ANCHOR_HOLES,
    EDGE_FACTOR,
    SPACING_FACTOR,
    Reject,
    check_detailing,
    sample_base_plate,
    write_construction_set,
)
from edp_eval.synth.dxf_writer import verify
from edp_eval.synth.labels import SyntheticLabel
from edp_eval.synth.parts import Hole, Plate


def test_base_plates_follow_the_detailing_rules():
    for i in range(40):
        plate = sample_base_plate(random.Random(i))
        assert plate.holes and all(h.diameter in ANCHOR_HOLES.values() for h in plate.holes)
        for h in plate.holes:
            assert min(h.x, h.y, plate.length - h.x, plate.width - h.y) >= EDGE_FACTOR * h.diameter
        for a in plate.holes:
            for b in plate.holes:
                if a is not b:
                    assert ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5 >= SPACING_FACTOR * a.diameter


def test_detailing_check_rejects_a_hole_too_close_to_the_edge():
    with pytest.raises(Reject):
        check_detailing(Plate(300.0, 300.0, 20.0, (Hole(20.0, 150.0, 22.0),)))


def test_construction_set_is_labelled_and_read_with_outline_roles(tmp_path):
    manifest = write_construction_set(tmp_path, 3, seed=11, uri_prefix="s3://edp-fabric/golden/construction")
    assert {i.part_family for i in manifest.items} == {"base_plate"}
    for path in sorted(tmp_path.glob("*.dxf")):
        label = SyntheticLabel.model_validate_json(
            path.with_suffix(".labels.json").read_text(encoding="utf-8")
        )
        assert verify(path, label) == []
        assert label.title_block["material"].value in ("S275JR", "S355JR", "S355J2")
        geometry, _, _ = dxf.parse(path.read_bytes(), "f", "c")
        graph, flags, _ = interpret(geometry)
        roles = {
            n.attributes["role"]: n.attributes["value_mm"] for n in graph.nodes if n.attributes.get("role")
        }
        assert roles == {
            "length": label.parameters["length"],
            "width": label.parameters["width"],
            "thickness": label.parameters["thickness"],
        }
        assert not [f for f in flags if f.severity != "info"]

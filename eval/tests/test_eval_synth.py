import json
from pathlib import Path

import ezdxf
import pytest

from edp_eval.golden import GoldenManifest
from edp_eval.metrics import Dimension, dimension_f1, title_block_accuracy
from edp_eval.synth import write_set
from edp_eval.synth.dxf_writer import generate, verify
from edp_eval.synth.labels import SyntheticLabel
from edp_eval.synth.profiles import PROFILES

PREFIX = "s3://edp-fabric/golden/synthetic"


@pytest.fixture(scope="module")
def small_set(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, GoldenManifest]:
    out = tmp_path_factory.mktemp("synth")
    return out, write_set(out, 8, seed=7, uri_prefix=PREFIX)


def _labels(out: Path) -> list[SyntheticLabel]:
    return [
        SyntheticLabel.model_validate_json(p.read_text(encoding="utf-8"))
        for p in sorted(out.glob("*.labels.json"))
    ]


def test_every_label_matches_its_dxf(small_set):
    out, _ = small_set
    labels = _labels(out)
    assert len(labels) == 8
    for label in labels:
        assert verify(out / f"{label.id}.dxf", label) == []


def test_set_covers_both_profiles_and_families(small_set):
    out, _ = small_set
    combos = {(lb.profile, lb.family) for lb in _labels(out)}
    assert combos == {("iso", "plate"), ("asme", "plate"), ("iso", "bracket"), ("asme", "bracket")}


def test_profiles_set_units_and_projection(small_set):
    out, _ = small_set
    for label in _labels(out):
        doc = ezdxf.readfile(out / f"{label.id}.dxf")
        p = PROFILES[label.profile]  # type: ignore[index]
        assert label.units == p.units and doc.header["$INSUNITS"] == p.insunits
        assert label.title_block["units"].value == p.units.upper()
        assert any(
            e.dxf.text == f"{p.projection.replace('_', ' ').upper()} PROJECTION"
            for e in doc.modelspace().query("TEXT")
        )


def test_plan_view_placement_follows_projection():
    # First angle puts the view from above below the front view; third angle puts it above.
    for name, below in (("iso", True), ("asme", False)):
        doc, label = generate(PROFILES[name], "plate", 0, seed=1)  # type: ignore[index]
        width_dim = next(d for d in label.dimensions if d.target == "plate.width")
        y = doc.entitydb[width_dim.handle].dxf.defpoint2.y  # type: ignore[union-attr]
        assert (y < 0) is below


def test_generation_is_deterministic():
    _, a = generate(PROFILES["iso"], "bracket", 3, seed=11)
    _, b = generate(PROFILES["iso"], "bracket", 3, seed=11)
    assert a.parameters == b.parameters
    assert [(d.target, d.value) for d in a.dimensions] == [(d.target, d.value) for d in b.dimensions]


def test_every_dimension_and_title_field_has_a_handle(small_set):
    out, _ = small_set
    for label in _labels(out):
        assert label.dimensions and all(d.handle for d in label.dimensions)
        assert set(label.title_block) == {
            "part_number",
            "revision",
            "material",
            "scale",
            "units",
            "tolerances",
        }
        targets = [d.target for d in label.dimensions]
        assert len(targets) == len(set(targets))


def test_manifest_validates_and_counts_toward_phase0(small_set):
    out, manifest = small_set
    reloaded = GoldenManifest.model_validate(json.loads((out / "manifest.json").read_text(encoding="utf-8")))
    assert reloaded == manifest
    check = manifest.phase0_exit_check()
    assert check.labelled_drawings == 8 and not check.passed  # 8 < 60
    assert all(
        i.data_uri.startswith(PREFIX + "/") and i.provenance.kind == "internal" for i in manifest.items
    )


def test_labels_feed_the_phase2_metrics(small_set):
    out, _ = small_set
    label = _labels(out)[0]
    truth = [Dimension(target=d.target, value=d.value) for d in label.dimensions]
    assert dimension_f1(truth, truth, value_tol=1e-9).f1 == 1.0
    fields = {k: v.value for k, v in label.title_block.items()}
    assert title_block_accuracy(fields, fields) == 1.0


def test_displayed_text_check_catches_a_scaled_dimension_style():
    # The ezdxf "EZDXF" style ships with dimlfac = 100; text drawn with it shows 100x the value.
    from edp_eval.synth.dxf_writer import _displayed_value

    doc = ezdxf.new("R2010", setup=True)
    dim = doc.modelspace().add_linear_dim(base=(0, -10), p1=(0, 0), p2=(80, 0), dimstyle="EZDXF")
    dim.render()
    assert _displayed_value(dim.dimension) == 8000.0

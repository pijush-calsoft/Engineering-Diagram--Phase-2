from pathlib import Path

import pytest
from pydantic import ValidationError

from edp_eval.golden import (
    COUNTED_MODEL_FORMATS,
    DRAWING_FORMATS,
    GoldenItem,
    GoldenManifest,
    Provenance,
)

EXAMPLE = Path(__file__).resolve().parents[1] / "golden" / "manifest.example.json"


def item(id: str, fmt: str = "dxf", labelled: bool = True, **kw) -> GoldenItem:
    base = {
        "id": id,
        "input_format": fmt,
        "part_family": "fam",
        "provenance": {"kind": "internal"},
        "data_uri": f"s3://edp-fabric/test/{id}",
        "labelled": labelled,
    }
    if labelled:
        base["ground_truth_uri"] = f"s3://edp-fabric/test/labels/{id}.json"
        base["label_fields"] = ["dimensions"]
    return GoldenItem(**{**base, **kw})


def test_example_manifest_validates():
    m = GoldenManifest.from_json_file(EXAMPLE)
    assert [i.id for i in m.items] == ["example-001", "example-002", "example-003"]
    check = m.phase0_exit_check()
    # example-001 (dxf, labelled), example-002 (scan, not labelled) -> 1 of 2 drawings labelled
    assert (check.labelled_drawings, check.total_drawings) == (1, 2)
    # example-003 (step, not labelled) -> 0 of 1 models labelled
    assert (check.labelled_models, check.total_models) == (0, 1)
    assert check.labelled_drawings_within_range is False
    assert check.passed is False
    assert check.models_target_met is False
    # The shared example holds no client-scoped item (plan Phase 0 task 2, principle 7).
    assert all(i.provenance.kind in {"internal", "open"} for i in m.items)
    assert (check.client_labelled_drawings, check.client_labelled_models) == (0, 0)


def test_format_groups():
    assert DRAWING_FORMATS == {"dxf", "dwg", "pdf_vector", "scan"}
    assert COUNTED_MODEL_FORMATS == {"step", "stl"}
    assert "iges" not in DRAWING_FORMATS | COUNTED_MODEL_FORMATS


def test_provenance_rules():
    Provenance(kind="internal")
    Provenance(kind="open", licence="some-licence")
    Provenance(kind="client", client_scope="scope-a")
    with pytest.raises(ValidationError, match="licence"):
        Provenance(kind="open")
    with pytest.raises(ValidationError, match="licence"):
        Provenance(kind="open", licence="  ")
    with pytest.raises(ValidationError, match="client_scope"):
        Provenance(kind="client")
    with pytest.raises(ValidationError):
        Provenance(kind="vendor")
    # A scope tag belongs to client items only.
    with pytest.raises(ValidationError, match="client_scope is only allowed"):
        Provenance(kind="internal", client_scope="scope-a")
    with pytest.raises(ValidationError, match="client_scope is only allowed"):
        Provenance(kind="open", licence="some-licence", client_scope="scope-a")


def test_item_validation():
    with pytest.raises(ValidationError):
        item("a", fmt="pdf")                          # not an R1 input type
    with pytest.raises(ValidationError, match="s3://"):
        item("a", data_uri="/local/path.dxf")         # data lives in the fabric
    with pytest.raises(ValidationError, match="s3://"):
        item("a", data_uri="s3://")
    with pytest.raises(ValidationError, match="ground_truth_uri"):
        GoldenItem(
            id="a", input_format="dxf", part_family="f", provenance={"kind": "internal"},
            data_uri="s3://x/a", labelled=True, label_fields=["geometry"],
        )
    with pytest.raises(ValidationError, match="label_fields"):
        item("a", label_fields=[])
    with pytest.raises(ValidationError, match="duplicate label_fields"):
        item("a", label_fields=["dimensions", "dimensions"])
    with pytest.raises(ValidationError):
        item("a", label_fields=["colour"])            # not a Phase 0 task 2 category
    with pytest.raises(ValidationError):
        item("")
    with pytest.raises(ValidationError):
        item("   ")                                   # whitespace-only id
    with pytest.raises(ValidationError):
        item("a", part_family="")
    with pytest.raises(ValidationError):
        item("a", part_family="  ")
    with pytest.raises(ValidationError, match="s3://"):
        item("a", data_uri="s3:// ")
    with pytest.raises(ValidationError, match="s3://"):
        item("a", data_uri=" s3://x/a")
    with pytest.raises(ValidationError, match="not labelled but lists label_fields"):
        item("a", labelled=False, label_fields=["material"])
    assert item(" a ", data_uri="s3://x/a").id == "a"  # ids are stripped
    unlabelled = item("b", labelled=False)
    assert unlabelled.ground_truth_uri is None and unlabelled.is_drawing


def test_duplicate_ids_rejected():
    with pytest.raises(ValidationError, match="duplicate item ids: \\['a'\\]"):
        GoldenManifest(version="v1", items=[item("a"), item("b"), item("a")])
    with pytest.raises(ValidationError, match="duplicate item ids: \\['a'\\]"):
        GoldenManifest(version="v1", items=[item("a"), item(" a ", data_uri="s3://x/a2")])


def test_phase0_exit_check_counts():
    # 15 labelled per 2D format = 60 labelled drawings, plus 1 unlabelled scan.
    items = [item(f"{fmt}-{n}", fmt=fmt) for fmt in ("dxf", "dwg", "pdf_vector", "scan") for n in range(15)]
    items.append(item("scan-x", fmt="scan", labelled=False))
    # 10 step + 10 stl labelled = 20 models; 3 iges labelled are not counted as models.
    items += [item(f"step-{n}", fmt="step") for n in range(10)]
    items += [item(f"stl-{n}", fmt="stl") for n in range(10)]
    items += [item(f"iges-{n}", fmt="iges") for n in range(3)]
    check = GoldenManifest(version="v1", items=items).phase0_exit_check()

    assert check.labelled_drawings == 60          # 4 formats x 15
    assert check.total_drawings == 61             # 60 + 1 unlabelled scan
    assert check.passed is True                   # 60 >= 60
    assert check.labelled_models == 20            # 10 + 10, iges excluded
    assert check.total_models == 20
    assert check.models_target_met is True        # 20 >= 20
    assert check.labelled_by_format == {
        "dwg": 15, "dxf": 15, "iges": 3, "pdf_vector": 15, "scan": 15, "step": 10, "stl": 10,
    }
    assert check.labelled_drawings_by_field == {"dimensions": 60}
    assert check.total_drawings_within_range is True  # 60 <= 61 <= 100
    assert check.labelled_drawings_within_range is True  # 60 <= 60 <= 100
    assert (check.client_labelled_drawings, check.client_labelled_models) == (0, 0)


def test_phase0_exit_check_ignores_client_items():
    # Plan Phase 0 task 2: "Use only internal or openly licensed drawings; client
    # drawings are used only inside that client's scope."
    # 60 labelled client drawings and 20 client models alone must not pass.
    client = {"provenance": {"kind": "client", "client_scope": "scope-a"}}
    items = [item(f"c-{n}", **client) for n in range(60)]
    items += [item(f"cm-{n}", fmt="step", **client) for n in range(20)]
    check = GoldenManifest(version="v1", items=items).phase0_exit_check()
    assert (check.labelled_drawings, check.total_drawings, check.passed) == (0, 0, False)
    assert (check.labelled_models, check.models_target_met) == (0, False)
    assert (check.client_labelled_drawings, check.client_labelled_models) == (60, 20)
    assert check.labelled_by_format == {}

    # 59 internal + 1 open labelled drawings pass; the client items stay separate.
    items += [item(f"i-{n}") for n in range(59)]
    items.append(item("o-0", fmt="pdf_vector", provenance={"kind": "open", "licence": "some-licence"}))
    check = GoldenManifest(version="v1", items=items).phase0_exit_check()
    assert (check.labelled_drawings, check.passed) == (60, True)
    assert check.client_labelled_drawings == 60


def test_phase0_exit_check_range_and_fields():
    # 101 shared drawings: above the task-2 range; information only, passed stays True.
    items = [item(f"d-{n}", label_fields=["dimensions", "title_block"]) for n in range(60)]
    items += [item(f"u-{n}", labelled=False) for n in range(41)]
    check = GoldenManifest(version="v1", items=items).phase0_exit_check()
    assert check.total_drawings == 101
    assert check.total_drawings_within_range is False
    assert check.labelled_drawings_within_range is True   # 60 labelled: the two readings differ
    assert check.passed is True
    assert check.labelled_drawings_by_field == {"dimensions": 60, "title_block": 60}
    # 59 shared drawings: below the range.
    check = GoldenManifest(version="v1", items=items[:59]).phase0_exit_check()
    assert check.total_drawings_within_range is False
    assert check.labelled_drawings_within_range is False


def test_phase0_exit_check_one_short():
    # 59 labelled drawings -> fails; 19 models -> target not met
    items = [item(f"d-{n}") for n in range(59)] + [item(f"m-{n}", fmt="stl") for n in range(19)]
    check = GoldenManifest(version="v1", items=items).phase0_exit_check()
    assert (check.labelled_drawings, check.passed) == (59, False)
    assert (check.labelled_models, check.models_target_met) == (19, False)


def test_empty_manifest():
    check = GoldenManifest(version="v0").phase0_exit_check()
    assert check.labelled_drawings == 0 and check.passed is False
    assert check.labelled_by_format == {}

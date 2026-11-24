import inspect

import pytest

from edp_contracts import SourceLocator
from edp_contracts.artifacts.geometry import GeometryEntity
from edp_eval.metrics import (
    PHASE2_TARGETS,
    Dimension,
    dimension_f1,
    expected_calibration_error,
    locator_coverage,
    title_block_accuracy,
)


def d(target: str, value: float) -> Dimension:
    return Dimension(target=target, value=value)


# --- targets -------------------------------------------------------------

def test_phase2_targets_match_plan_table():
    t = PHASE2_TARGETS
    assert (t["dimension_f1"].vector, t["dimension_f1"].scan) == (0.95, 0.85)
    assert (t["title_block_accuracy"].vector, t["title_block_accuracy"].scan) == (0.98, 0.92)
    assert (t["locator_coverage"].vector, t["locator_coverage"].scan) == (1.0, 1.0)
    assert (t["ece"].vector, t["ece"].scan) == (0.05, 0.08)
    assert t["dimension_f1"].met(0.95, "vector") and not t["dimension_f1"].met(0.94, "vector")
    assert t["ece"].met(0.08, "scan") and not t["ece"].met(0.081, "scan")


def test_tolerance_and_bins_have_no_default():
    assert inspect.signature(dimension_f1).parameters["value_tol"].default is inspect.Parameter.empty
    ece_params = inspect.signature(expected_calibration_error).parameters
    assert ece_params["n_bins"].default is inspect.Parameter.empty


# --- dimension F1 --------------------------------------------------------

def test_dimension_f1_hand_computed():
    truth = [d("f1", 10.0), d("f2", 20.0), d("f3", 5.0)]
    pred = [d("f1", 10.05), d("f2", 20.5), d("f4", 5.0), d("f1", 10.0)]
    r = dimension_f1(pred, truth, value_tol=0.1)
    # f1: pred[3] (diff 0) wins over pred[0] (diff 0.05); pred[0] has no truth left.
    # f2: diff 0.5 > 0.1, no match. f4: no truth with that target. f3: no prediction.
    # TP = 1; precision = 1/4; recall = 1/3; F1 = 2 * (1/12) / (7/12) = 2/7
    assert r.true_positives == 1
    assert r.precision == pytest.approx(0.25)
    assert r.recall == pytest.approx(1 / 3)
    assert r.f1 == pytest.approx(2 / 7)


def test_dimension_f1_reversed_same_result_without_ties():
    # No tied differences in this data, so reversing the predictions gives the
    # same result. This is NOT a general property; see the next test.
    truth = [d("f1", 10.0), d("f2", 20.0), d("f3", 5.0)]
    pred = [d("f1", 10.05), d("f2", 20.5), d("f4", 5.0), d("f1", 10.0)]
    a = dimension_f1(pred, truth, value_tol=0.1)
    b = dimension_f1(list(reversed(pred)), truth, value_tol=0.1)
    assert a == b


def test_dimension_f1_greedy_is_order_dependent_on_ties():
    # Documents a known limit of greedy matching (see dimension_f1 docstring).
    # Truth a=10.0 (t0), a=10.2 (t1); predictions a=10.1 (p0), a=9.9 (p1); tol 0.2.
    # In floating point, (p0,t0), (p0,t1) and (p1,t0) all have the same difference;
    # (p1,t1) = 0.3 > 0.2 is out. Ties break by prediction index.
    # Order [10.1, 9.9]: p0 takes t0 first, p1 has nothing left -> TP = 1.
    # Order [9.9, 10.1]: 9.9 takes t0, 10.1 takes t1 -> TP = 2 (the maximum).
    truth = [d("a", 10.0), d("a", 10.2)]
    pred = [d("a", 10.1), d("a", 9.9)]
    assert dimension_f1(pred, truth, value_tol=0.2).true_positives == 1
    assert dimension_f1(list(reversed(pred)), truth, value_tol=0.2).true_positives == 2


def test_dimension_f1_one_to_one_and_inclusive_tol():
    # Two truth dimensions on the same target, one prediction: only one match.
    truth = [d("h1", 8.0), d("h1", 8.0)]
    r = dimension_f1([d("h1", 8.5)], truth, value_tol=0.5)
    # |8.5 - 8.0| = 0.5 <= 0.5 matches; TP = 1; P = 1/1; R = 1/2; F1 = 2*1*0.5/1.5 = 2/3
    assert (r.true_positives, r.precision, r.recall) == (1, 1.0, 0.5)
    assert r.f1 == pytest.approx(2 / 3)


def test_dimension_f1_greedy_picks_closest_pair():
    # Truth 10.0 and 10.4 on target a; predictions 10.3 and 10.1, tol 0.35.
    # Pairs within tol: (10.3,10.0)=0.3, (10.3,10.4)=0.1, (10.1,10.0)=0.1, (10.1,10.4)=0.3.
    # Sorted: 0.1 (p0,t1), 0.1 (p1,t0) both accepted -> TP = 2, F1 = 1.
    r = dimension_f1([d("a", 10.3), d("a", 10.1)], [d("a", 10.0), d("a", 10.4)], value_tol=0.35)
    assert r.true_positives == 2 and r.f1 == pytest.approx(1.0)


def test_dimension_f1_perfect_and_no_predictions():
    truth = [d("a", 1.0), d("b", 2.0)]
    assert dimension_f1(truth, truth, value_tol=0.0).f1 == 1.0
    r = dimension_f1([], truth, value_tol=0.1)
    assert (r.precision, r.recall, r.f1, r.n_truth) == (0.0, 0.0, 0.0, 2)


def test_dimension_f1_errors():
    with pytest.raises(ValueError, match="truth is empty"):
        dimension_f1([d("a", 1.0)], [], value_tol=0.1)
    with pytest.raises(ValueError, match="truth is empty"):
        dimension_f1([], [], value_tol=0.1)
    with pytest.raises(ValueError, match="value_tol"):
        dimension_f1([], [d("a", 1.0)], value_tol=-0.1)
    with pytest.raises(TypeError):
        dimension_f1([], [d("a", 1.0)])  # type: ignore[call-arg]


# --- title block ---------------------------------------------------------

def test_title_block_accuracy_hand_computed():
    truth = {"part_number": "A-100", "revision": "B", "material": "S355", "scale": "1:2"}
    pred = {"part_number": " A-100 ", "revision": "C", "material": "S355", "units": "mm"}
    # part_number matches after strip, material matches; revision wrong; scale missing.
    # "units" is not in truth and is ignored. 2 / 4 = 0.5
    assert title_block_accuracy(pred, truth) == 0.5


def test_title_block_accuracy_exact_and_none():
    assert title_block_accuracy({"material": "s355"}, {"material": "S355"}) == 0.0   # case matters
    assert title_block_accuracy({"material": None}, {"material": "S355"}) == 0.0
    assert title_block_accuracy({"scale": "1:2"}, {"scale": " 1:2"}) == 1.0
    assert title_block_accuracy({}, {"scale": "1:2"}) == 0.0   # empty prediction scores 0, no error
    with pytest.raises(ValueError):
        title_block_accuracy({"scale": "1:2"}, {})


# --- locator coverage ----------------------------------------------------

def test_locator_coverage_hand_computed():
    loc = SourceLocator(file_id="f", version="c", confidence=0.9)
    entities = [
        GeometryEntity(kind="line", locator=loc),
        {"kind": "arc", "locator": {"file_id": "f"}},
        {"kind": "text", "locator": None},
        {"kind": "circle"},
    ]
    # 2 of 4 have a non-None locator -> 0.5
    assert locator_coverage(entities) == 0.5
    # Validated GeometryEntity objects always carry a locator, so they always score 1.0.
    assert locator_coverage([GeometryEntity(kind="line", locator=loc)]) == 1.0
    with pytest.raises(ValueError):
        locator_coverage([])


# --- ECE -----------------------------------------------------------------

def test_ece_hand_computed():
    conf = [0.9, 0.9, 0.8, 0.3]
    ok = [True, True, False, False]
    # n_bins = 2: bin [0, 0.5) = {0.3 wrong}: acc 0, conf 0.3, |0 - 0.3| = 0.3, weight 1/4 -> 0.075
    # bin [0.5, 1] = {0.9 ok, 0.9 ok, 0.8 wrong}: acc 2/3, conf 2.6/3, |2/3 - 2.6/3| = 0.6/3 = 0.2,
    # weight 3/4 -> 0.15. ECE = 0.075 + 0.15 = 0.225
    assert expected_calibration_error(conf, ok, n_bins=2) == pytest.approx(0.225)
    # n_bins = 1: acc 2/4 = 0.5, conf 2.9/4 = 0.725, ECE = |0.5 - 0.725| = 0.225 (same by coincidence)
    assert expected_calibration_error(conf, ok, n_bins=1) == pytest.approx(0.225)


def test_ece_edges():
    # 1.0 goes to the last bin; all correct at 1.0 is perfectly calibrated.
    assert expected_calibration_error([1.0, 1.0], [True, True], n_bins=10) == 0.0
    # 0.0 confidence and wrong is perfectly calibrated too.
    assert expected_calibration_error([0.0], [False], n_bins=5) == 0.0
    # Single item at 0.6, correct: |1 - 0.6| = 0.4
    assert expected_calibration_error([0.6], [True], n_bins=10) == pytest.approx(0.4)


def test_ece_bin_boundary_is_float_safe():
    # int(0.57 * 100) == 56 in floating point; 0.57 must still land in bin 57.
    # 0.565 is in bin 56 and is correct; 0.57 is in bin 57 and is wrong.
    # Separate bins: (1/2)*|1 - 0.565| + (1/2)*|0 - 0.57| = 0.2175 + 0.285 = 0.5025.
    # If 0.57 fell into bin 56 the two would share a bin:
    # |1/2 - 0.5675| = 0.0675, which this test would catch.
    assert int(0.57 * 100) == 56
    ece = expected_calibration_error([0.565, 0.57], [True, False], n_bins=100)
    assert ece == pytest.approx(0.5025)
    # Same check for 0.29 (int(0.29 * 100) == 28).
    ece = expected_calibration_error([0.285, 0.29], [True, False], n_bins=100)
    assert ece == pytest.approx(0.5 * 0.715 + 0.5 * 0.29)


def test_ece_errors():
    with pytest.raises(ValueError, match="empty"):
        expected_calibration_error([], [], n_bins=10)
    with pytest.raises(ValueError, match="same length"):
        expected_calibration_error([0.5], [True, False], n_bins=10)
    with pytest.raises(ValueError, match="n_bins"):
        expected_calibration_error([0.5], [True], n_bins=0)
    with pytest.raises(ValueError, match="outside"):
        expected_calibration_error([1.2], [True], n_bins=10)

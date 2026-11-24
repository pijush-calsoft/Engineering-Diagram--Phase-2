"""Parser metrics for the golden set.

Source: plan Phase 2 exit criteria table and plan section 7 ("Parser" row:
dimension F1, title block accuracy, locator coverage, calibration; tooling
"pytest + custom metrics on golden set").

Plain Python, no data needed. Metrics for the other layers in the section 7
table (interpretation, generation, solvers, surrogate, reports, orchestrator,
gateway) come in their own phases.

Plan section 7: "Targets in section 6 are proposals to confirm in Phase 0."
"""

from bisect import bisect_right
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

InputClass = Literal["vector", "scan"]


@dataclass(frozen=True)
class Target:
    op: Literal[">=", "<="]
    vector: float                      # plan column "Vector DXF / PDF"
    scan: float                        # plan column "Scans"

    def met(self, value: float, input_class: InputClass) -> bool:
        threshold = self.vector if input_class == "vector" else self.scan
        return value >= threshold if self.op == ">=" else value <= threshold


# Source: plan Phase 2 "Exit criteria (on golden set)" table.
# Proposals to confirm in Phase 0 (plan section 7).
PHASE2_TARGETS: dict[str, Target] = {
    "dimension_f1": Target(">=", vector=0.95, scan=0.85),           # Dimension value and target F1
    "title_block_accuracy": Target(">=", vector=0.98, scan=0.92),   # Title block field accuracy
    "locator_coverage": Target(">=", vector=1.0, scan=1.0),         # Entities with a valid source locator
    "ece": Target("<=", vector=0.05, scan=0.08),                    # Calibration error (ECE) on confidences
}


class Dimension(BaseModel):
    target: str                        # id of the feature the dimension measures (Phase 2 task 2)
    value: float


class PRF(BaseModel):
    precision: float
    recall: float
    f1: float
    true_positives: int
    n_predicted: int
    n_truth: int


def dimension_f1(predicted: Sequence[Dimension], truth: Sequence[Dimension], *, value_tol: float) -> PRF:
    """Dimension value and target F1 (plan Phase 2 exit table; target >= 0.95 vector, >= 0.85 scans).

    A prediction matches a truth item when the targets are equal and
    ``|predicted.value - truth.value| <= value_tol``. Matching is one-to-one and
    greedy: all candidate pairs are sorted by value difference (ties by
    prediction index, then truth index) and accepted while both sides are free.

    Greedy matching is not a maximum matching. It can undercount true
    positives, and when differences tie the result depends on the order of
    ``predicted``. Example: truth a=10.0 and a=10.2, predictions a=10.1 and
    a=9.9, ``value_tol=0.2``: TP is 1 in that order and 2 when the predictions
    are reversed. The plan does not give a matching algorithm (Phase 2 exit
    table only names "Dimension value and target F1"). The algorithm and
    ``value_tol`` are not specified in plan or deck; TBD in Phase 0.

    ``value_tol`` has no default on purpose: the plan does not define the
    matching tolerance. Values are compared as given, so both sides must use
    the same units.

    Raises ValueError when ``truth`` is empty (recall is undefined) or
    ``value_tol`` is negative. An empty ``predicted`` does not raise: with a
    non-empty truth, precision, recall and F1 are all reported as 0.0. This is
    a design choice: a parser that finds nothing scores 0. Not specified in
    plan or deck; TBD in Phase 0.
    """
    if value_tol < 0:
        raise ValueError("value_tol must be >= 0")
    if not truth:
        raise ValueError("truth is empty; dimension F1 is undefined")

    candidates = [
        (abs(p.value - t.value), pi, ti)
        for pi, p in enumerate(predicted)
        for ti, t in enumerate(truth)
        if p.target == t.target and abs(p.value - t.value) <= value_tol
    ]
    candidates.sort()
    used_p: set[int] = set()
    used_t: set[int] = set()
    for _, pi, ti in candidates:
        if pi not in used_p and ti not in used_t:
            used_p.add(pi)
            used_t.add(ti)

    tp = len(used_p)
    precision = tp / len(predicted) if predicted else 0.0
    recall = tp / len(truth)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0.0
    return PRF(
        precision=precision,
        recall=recall,
        f1=f1,
        true_positives=tp,
        n_predicted=len(predicted),
        n_truth=len(truth),
    )


def title_block_accuracy(predicted: Mapping[str, str | None], truth: Mapping[str, str]) -> float:
    """Title block field accuracy (plan Phase 2 exit table; target >= 0.98 vector, >= 0.92 scans).

    Share of truth fields whose predicted value equals the truth value exactly
    after ``str.strip()`` on both sides. A missing or None prediction counts as
    wrong. Predicted fields that are not in ``truth`` are ignored.

    Raises ValueError when ``truth`` is empty. An empty ``predicted`` does not
    raise; every truth field then counts as wrong and the result is 0.0.
    """
    if not truth:
        raise ValueError("truth is empty; title block accuracy is undefined")
    correct = 0
    for name, expected in truth.items():
        got = predicted.get(name)
        if got is not None and got.strip() == expected.strip():
            correct += 1
    return correct / len(truth)


def locator_coverage(entities: Sequence[object]) -> float:
    """Share of entities with a non-None ``locator`` (plan Phase 2 exit table; target 100 %).

    The metric is meant for raw parser output, before validation. It accepts
    mappings with a ``"locator"`` key or objects with a ``locator`` attribute.
    Note that ``edp_contracts.artifacts.geometry.GeometryEntity`` declares
    ``locator`` as required, so a list of validated ``GeometryEntity`` objects
    always scores 1.0 and the metric says nothing new about them.

    This checks presence only; whether a locator resolves to a real file
    version in the Data Fabric is not checked here. Whether "valid" means more
    than present is not specified in plan or deck; TBD in Phase 0.

    Raises ValueError when ``entities`` is empty.
    """
    if not entities:
        raise ValueError("entities is empty; locator coverage is undefined")
    with_locator = 0
    for e in entities:
        loc = e.get("locator") if isinstance(e, Mapping) else getattr(e, "locator", None)
        if loc is not None:
            with_locator += 1
    return with_locator / len(entities)


def expected_calibration_error(confidences: Sequence[float], correct: Sequence[bool], n_bins: int) -> float:
    """Expected calibration error (plan Phase 2 exit table; target <= 0.05 vector, <= 0.08 scans).

    Plan Phase 2 task 5: "Confidence calibration per field so that 0.6 means
    roughly a 60 % chance of being right."

    ECE = sum over bins b of (|b| / N) * |accuracy(b) - mean confidence(b)|,
    with ``n_bins`` equal-width bins over [0, 1]. Bin i holds confidences in
    [i / n_bins, (i + 1) / n_bins); a confidence of exactly 1.0 goes to the
    last bin. Empty bins contribute nothing. The bin is found by comparing the
    confidence with the edges ``i / n_bins`` (``bisect``), not by
    ``int(c * n_bins)``: the product can round down, for example
    ``int(0.57 * 100) == 56``, which would put 0.57 one bin too low.

    ``n_bins`` has no default on purpose. The bin count is not specified in plan or
    deck; TBD in Phase 0.

    Raises ValueError on empty input, length mismatch, ``n_bins < 1`` or a
    confidence outside [0, 1].
    """
    if n_bins < 1:
        raise ValueError("n_bins must be >= 1")
    if not confidences:
        raise ValueError("confidences is empty; ECE is undefined")
    if len(confidences) != len(correct):
        raise ValueError("confidences and correct must have the same length")

    edges = [i / n_bins for i in range(n_bins + 1)]
    counts = [0] * n_bins
    conf_sums = [0.0] * n_bins
    hit_sums = [0] * n_bins
    for c, ok in zip(confidences, correct, strict=True):
        if not 0.0 <= c <= 1.0:
            raise ValueError(f"confidence {c!r} is outside [0, 1]")
        b = min(bisect_right(edges, c) - 1, n_bins - 1)
        counts[b] += 1
        conf_sums[b] += c
        hit_sums[b] += 1 if ok else 0

    n = len(confidences)
    ece = 0.0
    for count, conf_sum, hits in zip(counts, conf_sums, hit_sums, strict=True):
        if count:
            ece += (count / n) * abs(hits / count - conf_sum / count)
    return ece

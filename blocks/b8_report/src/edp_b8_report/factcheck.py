"""Run Store and fact checker for block 8 (plan Phase 6 Insight tasks 2 and 3; deck slide 40).

Run Store: the run's stored artifacts as JSON documents, keyed by artifact kind. A claim's
``run_store_ref`` is ``<kind>:<JSON pointer>``, for example
``solver_runs:/runs/0/max_von_mises_MPa``.

The checker blocks a report (plan Phase 6 Insight task 3; deck slide 40 "a mismatch blocks
release") when:

1. a claim's reference does not resolve, or resolves to a different value;
2. a section cites a claim id the report does not hold (``Report.unresolved_claim_ids``);
3. a number appears in a section's text that is not the printed form of a claim that section
   cites (AC-P6-02: every number comes from the Run Store, never typed). Identifiers such as
   part numbers and load-case ids are removed before numbers are looked for.
"""

import math
import re
from typing import Any

from edp_contracts.artifacts.report import NumericClaim, Report

NUMBER = re.compile(r"(?<![A-Za-z0-9_.-])-?\d+(?:[.,]\d+)?(?![A-Za-z0-9_])")


class RunStore:
    def __init__(self, documents: dict[str, Any]) -> None:
        self.documents = documents

    def resolve(self, ref: str) -> Any:
        kind, _, pointer = ref.partition(":")
        if kind not in self.documents:
            raise KeyError(f"no {kind!r} document in the Run Store")
        node: Any = self.documents[kind]
        for raw in [p for p in pointer.split("/") if p]:
            part = raw.replace("~1", "/").replace("~0", "~")
            node = node[int(part)] if isinstance(node, list) else node[part]
        return node


def fmt(value: float) -> str:
    """How a claim is printed: three significant figures, no exponent."""
    if value == 0:
        return "0"
    digits = max(0, 2 - int(math.floor(math.log10(abs(value)))))
    text = f"{value:.{digits}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def check(report: Report, store: RunStore, identifiers: list[str]) -> list[str]:
    problems: list[str] = []
    claims = {c.id: c for c in report.claims}
    for c in report.claims:
        try:
            stored = float(store.resolve(c.run_store_ref))
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            problems.append(f"{c.id}: reference {c.run_store_ref} does not resolve ({exc})")
            continue
        if not math.isclose(stored, c.value, rel_tol=1e-9, abs_tol=1e-12):
            problems.append(f"{c.id}: report says {c.value}, Run Store holds {stored}")
    for cid in sorted(report.unresolved_claim_ids()):
        problems.append(f"section cites unknown claim {cid}")
    for s in report.sections:
        allowed = {fmt(claims[cid].value) for cid in s.claim_ids if cid in claims}
        text = s.text
        if "{" in text or "}" in text:
            problems.append(f"section {s.key}: unfilled placeholder in the text")
        for ident in sorted(identifiers, key=len, reverse=True):
            if ident:
                text = text.replace(ident, " ")
        for m in NUMBER.finditer(text):
            token = m.group().replace(",", ".")
            if token not in allowed:
                problems.append(f"section {s.key}: number {m.group()} is not a cited Run Store value")
    return problems


def claim(cid: str, ref: str, store: RunStore, unit: str | None) -> NumericClaim:
    return NumericClaim(id=cid, value=float(store.resolve(ref)), unit=unit, run_store_ref=ref)

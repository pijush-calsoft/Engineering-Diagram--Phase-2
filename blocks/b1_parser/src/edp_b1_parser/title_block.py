"""Title-block extraction from drawing text, deterministic first (plan principle 2, Phase 2 task 3).

Fields: part number, revision, material, scale, units, tolerances (plan Phase 2
task 3). This rule reads "LABEL: value" text. Layouts it cannot read (separate
label and value cells, scans) go to the multimodal model later (ADR-0007).

Confidence: 1.0 when exactly one value is found for a field, 0.5 when several
different values compete (and a ``LOW_CONFIDENCE`` flag is raised). These are
starting values; plan Phase 2 task 5 calibrates them, measured by ECE on the
golden set.
"""

import re
from dataclasses import dataclass

from edp_contracts import Flag, SourceLocator
from edp_contracts.artifacts.geometry import TitleBlock, TitleBlockField

_LABELS: dict[str, str] = {
    r"PART\s*(?:NO\.?|NUMBER|NUM\.?)": "part_number",
    r"REV(?:ISION)?\.?": "revision",
    r"MATERIAL|MATL\.?": "material",
    r"SCALE": "scale",
    r"UNITS?": "units",
    r"(?:GENERAL\s+)?TOLERANCES?": "tolerances",
}
_PATTERN = re.compile(
    r"^\s*(?P<label>" + "|".join(f"(?:{p})" for p in _LABELS) + r")\s*[:=]\s*(?P<value>.+?)\s*$",
    re.IGNORECASE,
)
UNIQUE_CONFIDENCE = 1.0
CONFLICT_CONFIDENCE = 0.5


@dataclass(frozen=True)
class TextItem:
    text: str
    locator: SourceLocator


def _field_name(label: str) -> str:
    for pattern, name in _LABELS.items():
        if re.fullmatch(pattern, label.strip(), re.IGNORECASE):
            return name
    raise KeyError(label)


def extract(texts: list[TextItem]) -> tuple[TitleBlock | None, list[Flag]]:
    found: dict[str, list[tuple[str, SourceLocator]]] = {}
    for item in texts:
        m = _PATTERN.match(item.text)
        if m:
            found.setdefault(_field_name(m["label"]), []).append((m["value"], item.locator))
    if not found:
        return None, []
    fields: dict[str, TitleBlockField] = {}
    flags: list[Flag] = []
    for name, hits in found.items():
        value, loc = hits[0]
        distinct = {v for v, _ in hits}
        confidence = UNIQUE_CONFIDENCE if len(distinct) == 1 else CONFLICT_CONFIDENCE
        if len(distinct) > 1:
            flags.append(
                Flag(
                    code="LOW_CONFIDENCE",
                    target=loc,
                    message=f"title block {name}: {len(distinct)} different values {sorted(distinct)}",
                )
            )
        fields[name] = TitleBlockField(value=value, locator=loc.model_copy(update={"confidence": confidence}))
    return TitleBlock(**fields), flags

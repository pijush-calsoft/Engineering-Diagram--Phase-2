"""Remove client-identifying and personal text before any model call.

OD-39 allows drawings to go to the OpenAI API for the POC, but organisation policy still
forbids client-identifying information and personal data in prompts to external systems.
Plan Phase 1 names Presidio for PII redaction; it needs a spaCy language model that is not
installed here, so this POC redactor is deterministic (OD-51):

1. terms listed in ``EDP_REDACT_TERMS`` (client and company names; kept only in ``.env``),
2. e-mail addresses, and phone numbers (8 or more digits) that start with ``+`` or follow a
   phone label,
3. the rest of a line after an identifying title-block label, such as ``DRAWN BY`` or
   ``CUSTOMER:`` (starting list, OD-51).

Plain numbers are never touched: drawing text is full of them. Callers should still send
only the text a task needs; this is the last line of defence, not the only one.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# No "." or "/" after a bare "+": tolerances such as "+0.1/-0.0" must survive.
_PHONE = re.compile(
    r"\+\d[\d ()-]{6,}\d|(?i:\b(?:tel|phone|ph|fax|mobile|mob)\b\.?\s*[:.]?\s*)[\d+()][\d ()./-]{6,}\d"
)
PHONE_MIN_DIGITS = 8  # fewer digits than this is not treated as a phone number
_LABEL = re.compile(
    r"(?im)\b(company|customer|client|vendor|supplier|drawn|checked|approved|designed|engineer|author)"
    r"(\s+by)?\s*[:=]\s*\S.*$"
    r"|\b(drawn|checked|approved|designed)\s+by\s+\S.*$"
)


@dataclass
class Redaction:
    text: str
    kinds: Counter[str] = field(default_factory=Counter)

    @property
    def count(self) -> int:
        return sum(self.kinds.values())


class Redactor:
    def __init__(self, terms: tuple[str, ...] = ()):
        longest_first = sorted({t for t in terms if t}, key=len, reverse=True)
        self._terms = (
            re.compile("|".join(re.escape(t) for t in longest_first), re.IGNORECASE)
            if longest_first
            else None
        )

    def __call__(self, text: str) -> Redaction:
        kinds: Counter[str] = Counter()

        def sub(pattern: re.Pattern[str], kind: str, s: str) -> str:
            out, n = pattern.subn(f"[REDACTED:{kind}]", s)
            kinds[kind] += n
            return out

        if self._terms:
            text = sub(self._terms, "term", text)
        text = sub(_EMAIL, "email", text)
        text = _PHONE.sub(lambda m: self._phone(m, kinds), text)
        text = _LABEL.sub(lambda m: self._label(m, kinds), text)
        return Redaction(text=text, kinds=+kinds)

    @staticmethod
    def _phone(m: re.Match[str], kinds: Counter[str]) -> str:
        if sum(c.isdigit() for c in m.group()) < PHONE_MIN_DIGITS:
            return m.group()
        kinds["phone"] += 1
        return "[REDACTED:phone]"

    @staticmethod
    def _label(m: re.Match[str], kinds: Counter[str]) -> str:
        kinds["title_block_field"] += 1
        label = (m.group(1) or m.group(3)).upper()
        return f"{label}: [REDACTED:title_block_field]"

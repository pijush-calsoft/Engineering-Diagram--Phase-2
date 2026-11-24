"""Licence gate for installed Python distributions (plan section 9).

Plan section 9: permissive licences are allowed anywhere, LGPL only as an unmodified
library, GPL tools only as separate processes or containers, AGPL never imported into
our services. "CI fails on unapproved licenses." Phase 0 exit criterion: "CI blocks any
AGPL dependency imported in-process."

Every distribution installed in the environment the gate runs in counts as
in-process. The gate reads each one's licence from its metadata, maps it to an
SPDX-like id, and classifies it against ``scripts/ci/license_policy.toml``. Exit code 1
means at least one distribution is denied in-process, or has a licence the gate cannot
map and that is not cleared by an ``[exceptions]`` entry. An exception is refused when
the metadata text names GPL, AGPL, SSPL, BSL/BUSL or RSAL (see ``mentions_denied``).

Usage: ``uv run python -m edp_ci.license_gate [--repo-root PATH] [--policy PATH] [--json]``.

Scope: Python distributions only. Containers, CLIs, npm packages, model weights and
datasets are out of reach here; see docs/policies/license-policy.md.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field
from importlib.metadata import PackageMetadata, distributions
from pathlib import Path
from typing import Literal

Category = Literal["allowed", "conditional", "denied_in_process", "unknown"]
Status = Literal["pass", "warn", "exception", "fail"]

# Policy file, relative to the repo root.
POLICY_RELPATH = Path("scripts") / "ci" / "license_policy.toml"


def _source_root() -> Path:
    """Repo root for an editable install: scripts/ci/src/edp_ci/license_gate.py -> four
    levels up. For any other install this path is wrong; see ``default_repo_root``."""
    parents = Path(__file__).resolve().parents
    return parents[4] if len(parents) > 4 else parents[-1]


# The workspace's own packages are read from the root pyproject.toml and not checked.
REPO_ROOT = _source_root()
DEFAULT_POLICY = REPO_ROOT / POLICY_RELPATH

# A "License" metadata field longer than this, or spanning lines, is treated as full
# licence text and skipped in favour of the classifiers.
SHORT_LICENSE_MAX = 100

# Worst-of / best-of ordering for AND / OR expressions.
_RANK: dict[Category, int] = {"allowed": 0, "conditional": 1, "unknown": 2, "denied_in_process": 3}

# Trove classifier leaves that are markers, not licences.
_CLASSIFIER_MARKERS = {"osi approved", "dfsg approved"}

# Metadata text -> SPDX-like id. Keys are matched after collapsing whitespace and
# case-folding. Only unambiguous names are mapped; anything else stays unknown.
# Unversioned names map to an unversioned id only where the policy has one
# ("BSD", "LGPL", "GPL", "AGPL", "SSPL", "BUSL", "RSAL"); for example "Apache Software
# License" without a version is left unknown, because plan section 9 names Apache 2.0
# only. Versioned RSAL text ("RSALv2") and LGPL v2 text that does not say 2.0 or 2.1
# also map to unversioned ids, because the policy has no matching versioned id.
# "BSL 1.0" is not mapped: BSL-1.0 is the SPDX id of the Boost Software License.
_ALIAS_GROUPS: dict[str, tuple[str, ...]] = {
    "MIT": ("mit license", "the mit license", "mit licence"),
    "BSD": ("bsd license", "bsd licence"),
    "BSD-2-Clause": ("bsd 2-clause", "bsd 2-clause license", "simplified bsd", "simplified bsd license"),
    "BSD-3-Clause": (
        "bsd 3-clause",
        "bsd 3-clause license",
        "3-clause bsd",
        "3-clause bsd license",
        "new bsd",
        "new bsd license",
        "modified bsd",
        "modified bsd license",
        "revised bsd license",
    ),
    "Apache-2.0": (
        "apache 2.0",
        "apache 2",
        "apache-2",
        "apache license 2.0",
        "apache license, version 2.0",
        "apache license version 2.0",
        "apache software license 2.0",
        "apache 2.0 license",
    ),
    "PostgreSQL": ("postgresql license",),
    "MPL-2.0": ("mpl 2.0", "mozilla public license 2.0", "mozilla public license 2.0 (mpl 2.0)"),
    "ISC": ("isc license", "isc license (iscl)"),
    "LGPL": (
        "gnu library or lesser general public license (lgpl)",
        "gnu lesser general public license v2 (lgplv2)",
        "gnu lesser general public license v2 or later (lgplv2+)",
    ),
    "LGPL-2.0-only": ("lgpl-2.0",),
    "LGPL-2.0-or-later": ("lgpl-2.0+",),
    "LGPL-2.1-only": ("lgpl-2.1", "lgplv2.1"),
    "LGPL-2.1-or-later": ("lgpl-2.1+", "lgplv2.1+"),
    "LGPL-3.0-only": ("lgpl-3.0", "lgplv3", "gnu lesser general public license v3 (lgplv3)"),
    "LGPL-3.0-or-later": ("lgpl-3.0+", "lgplv3+", "gnu lesser general public license v3 or later (lgplv3+)"),
    "GPL": ("gnu general public license", "gnu general public license (gpl)"),
    "GPL-2.0-only": ("gpl-2.0", "gplv2", "gnu general public license v2 (gplv2)"),
    "GPL-2.0-or-later": ("gpl-2.0+", "gplv2+", "gnu general public license v2 or later (gplv2+)"),
    "GPL-3.0-only": ("gpl-3.0", "gplv3", "gnu general public license v3 (gplv3)"),
    "GPL-3.0-or-later": ("gpl-3.0+", "gplv3+", "gnu general public license v3 or later (gplv3+)"),
    "AGPL": ("gnu affero general public license",),
    "AGPL-1.0-only": ("agpl-1.0",),
    "AGPL-3.0-only": ("agpl-3.0", "agplv3", "gnu affero general public license v3"),
    "AGPL-3.0-or-later": (
        "agpl-3.0+",
        "agplv3+",
        "gnu affero general public license v3 or later (agplv3+)",
    ),
    # SSPL, BUSL (BSL) and RSAL: derived from the plan section 9 watch-list (Redis 8+
    # "AGPL / SSPL / RSAL"; HashiCorp Vault and Terraform "BSL"). The plan gives no
    # version for any of them.
    "SSPL": ("sspl", "server side public license", "server side public license (sspl)"),
    "SSPL-1.0": ("sspl v1", "sspl 1.0", "sspl v1.0", "server side public license v1"),
    "BUSL": ("bsl", "busl", "business source license", "business source license (bsl)"),
    "BUSL-1.1": ("bsl-1.1", "bsl 1.1", "bsl v1.1", "business source license 1.1"),
    "BUSL-1.0": ("business source license 1.0",),
    "RSAL": (
        "rsal",
        "rsalv2",
        "redis source available license",
        "redis source available license 2.0",
        "redis source available license 2.0 (rsalv2)",
    ),
    # GPL-1.0: GPL per the plan section 9 policy text.
    "GPL-1.0-only": ("gpl-1.0", "gplv1"),
    "GPL-1.0-or-later": ("gpl-1.0+", "gplv1+"),
}

# SPDX exception ids accepted after WITH in a License-Expression. Any other right-hand
# side makes the term unknown (or keeps it denied when the left-hand side is denied).
# OCCT-exception-1.0: the SPDX id for the exception in plan section 4.2 "OCCT is
# LGPL 2.1 with exception". The plan does not give the id. Confirm in Phase 0.
SPDX_EXCEPTIONS: frozenset[str] = frozenset({"OCCT-exception-1.0"})

# Metadata text that names a licence the policy denies in-process. An [exceptions]
# entry is never honoured for a distribution whose licence text matches, even when
# the gate cannot map the text to an id (for example "GNU AGPLv3" or "SSPL v2").
# The text is checked one segment at a time (split on and/or/with, commas, slashes,
# semicolons, brackets, &, +, |, newlines and spaced dashes). Within a segment, a GPL
# match is skipped only when one of the three words just before it is "Lesser" or
# "Library", so "Lesser GPL & AGPL" still counts as denied.
_GPL_TEXT = re.compile(r"(?<![a-z])a?gpl|affero|general public licen[cs]e", re.IGNORECASE)
_LESSER_WORDS = frozenset({"lesser", "library"})
# SSPL, BSL/BUSL and RSAL (plan section 9 watch-list). "BSL 1.0" is skipped because
# BSL-1.0 is the SPDX id of the Boost Software License.
_OTHER_DENIED_TEXT = re.compile(
    r"(?<![a-z])(?:sspl|busl|rsal)"
    r"|server side public licen[cs]e|business source licen[cs]e|redis source available"
    r"|(?<![a-z])bsl(?![a-z])(?![\s_-]*v?1\.0(?![\d.]))",
    re.IGNORECASE,
)
_SEGMENT_SPLIT = re.compile(r"\s+(?:and|or|with)\s+|\s+-\s+|[(),;/&+|\n]", re.IGNORECASE)


def _key(text: str) -> str:
    return re.sub(r"[\s_]+", " ", text.strip()).casefold()


_ALIASES: dict[str, str] = {}
for _id, _names in _ALIAS_GROUPS.items():
    _ALIASES[_key(_id)] = _id
    for _name in _names:
        _ALIASES[_key(_name)] = _id


@dataclass(frozen=True)
class Policy:
    allowed: frozenset[str]
    conditional: frozenset[str]
    denied_in_process: frozenset[str]
    exceptions: dict[str, str] = field(default_factory=dict)

    def category_of(self, licence_id: str) -> Category:
        if licence_id in self.denied_in_process:
            return "denied_in_process"
        if licence_id in self.conditional:
            return "conditional"
        if licence_id in self.allowed:
            return "allowed"
        return "unknown"

    def known_ids(self) -> dict[str, str]:
        ids = self.allowed | self.conditional | self.denied_in_process
        return {_key(i): i for i in ids}


def load_policy(path: Path = DEFAULT_POLICY) -> Policy:
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    return Policy(
        allowed=frozenset(data.get("allowed", {}).get("ids", [])),
        conditional=frozenset(data.get("conditional", {}).get("ids", [])),
        denied_in_process=frozenset(data.get("denied_in_process", {}).get("ids", [])),
        exceptions={canonical_name(k): str(v) for k, v in data.get("exceptions", {}).items()},
    )


def canonical_name(name: str) -> str:
    """PEP 503 normalised distribution name."""
    return re.sub(r"[-_.]+", "-", name).lower()


def normalise(text: str, policy: Policy | None = None) -> str | None:
    """Map one licence name (SPDX id, short ``License`` text or classifier leaf) to an id.

    Returns ``None`` when the name is not recognised.
    """
    key = _key(text)
    if policy is not None and key in policy.known_ids():
        return policy.known_ids()[key]
    return _ALIASES.get(key)


# --- expression parsing ---------------------------------------------------------------

_TOKEN_SPLIT = re.compile(r"(\(|\)|\s+(?:AND|OR|WITH)\s+)", re.IGNORECASE)


class _ParseError(ValueError):
    pass


def _tokens(expr: str) -> list[str]:
    parts = [p.strip() for p in _TOKEN_SPLIT.split(expr)]
    return [p.upper() if p.upper() in {"AND", "OR", "WITH"} else p for p in parts if p]


def _worst(cats: list[Category]) -> Category:
    return max(cats, key=_RANK.__getitem__)


def _best(cats: list[Category]) -> Category:
    return min(cats, key=_RANK.__getitem__)


class _Evaluator:
    """Recursive descent over ``expr := term (OR term)*; term := factor (AND factor)*``."""

    def __init__(self, tokens: list[str], policy: Policy, spdx: bool) -> None:
        self.tokens = tokens
        self.pos = 0
        self.policy = policy
        self.spdx = spdx

    def _peek(self) -> str | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _take(self) -> str:
        tok = self._peek()
        if tok is None:
            raise _ParseError("unexpected end of expression")
        self.pos += 1
        return tok

    def run(self) -> Category:
        cat = self._expr()
        if self._peek() is not None:
            raise _ParseError(f"unexpected token {self._peek()!r}")
        return cat

    def _expr(self) -> Category:
        options = [self._term()]
        while self._peek() == "OR":
            self._take()
            options.append(self._term())
        return _best(options)

    def _term(self) -> Category:
        parts = [self._factor()]
        while self._peek() == "AND":
            self._take()
            parts.append(self._factor())
        return _worst(parts)

    def _factor(self) -> Category:
        tok = self._take()
        if tok == "(":
            cat = self._expr()
            if self._take() != ")":
                raise _ParseError("missing ')'")
            return cat
        if tok in {")", "AND", "OR", "WITH"}:
            raise _ParseError(f"unexpected token {tok!r}")
        licence_id = normalise(tok, self.policy)
        category: Category = self.policy.category_of(licence_id) if licence_id else "unknown"
        if self._peek() == "WITH":
            if not self.spdx:
                # Free text such as "Apache 2.0 with Commons Clause" is not SPDX; the
                # right-hand side may add restrictions.
                raise _ParseError("WITH outside a License-Expression")
            self._take()
            if self._take() not in SPDX_EXCEPTIONS:
                # Unrecognised exception: unknown, unless X is already denied.
                return _worst([category, "unknown"])
        return category


def classify(expr: str, policy: Policy, spdx: bool = True) -> Category:
    """Classify a licence expression against the policy.

    ``A OR B`` takes the best option (passes if any option is allowed); ``A AND B``
    takes the worst. Unrecognised names and unparseable text are ``unknown``.
    ``spdx`` is True only for a ``License-Expression`` field. ``X WITH E`` is read as
    ``X`` only then, and only when ``E`` is in ``SPDX_EXCEPTIONS``. In free text,
    ``WITH`` makes the result ``unknown``.
    """
    if not expr or not expr.strip():
        return "unknown"
    whole = normalise(expr, policy)
    if whole is not None:
        return policy.category_of(whole)
    try:
        return _Evaluator(_tokens(expr), policy, spdx).run()
    except _ParseError:
        return "unknown"


# --- reading metadata -----------------------------------------------------------------


def _first(meta: PackageMetadata, field_name: str) -> str:
    values = meta.get_all(field_name) or []
    return str(values[0]).strip() if values else ""


def licence_candidates(meta: PackageMetadata) -> list[tuple[str, str]]:
    """Licence statements in priority order, as ``(source, expression)`` pairs.

    1. ``License-Expression``; 2. ``License`` if short; 3. ``License ::`` classifiers.
    Several licence classifiers are combined with AND, the cautious reading.
    A ``License`` value of ``UNKNOWN`` (any case) is the placeholder older setuptools
    writes when no licence is set; it is treated as absent, like an empty value.
    """
    out: list[tuple[str, str]] = []
    expr = _first(meta, "License-Expression")
    if expr:
        out.append(("License-Expression", expr))
    lic = _first(meta, "License")
    if lic and lic.casefold() != "unknown" and "\n" not in lic and len(lic) <= SHORT_LICENSE_MAX:
        out.append(("License", lic))
    leaves = classifier_leaves(meta)
    if leaves:
        # Every leaf is joined with AND. An unmapped leaf stays as a raw token and
        # evaluates to unknown, so a GPL or AGPL leaf still makes the whole result
        # denied_in_process.
        out.append(("Classifier", " AND ".join(_classifier_token(leaf) for leaf in leaves)))
    return out


def _classifier_token(leaf: str) -> str:
    """Mapped id, or the raw leaf. A raw leaf that contains AND/OR/WITH or brackets
    is replaced by a placeholder that stays unknown, so it cannot be read as an
    operator."""
    mapped = normalise(leaf)
    if mapped:
        return mapped
    if len(_tokens(leaf)) != 1:
        return "LicenseRef-unmapped-classifier"
    return leaf


def classifier_leaves(meta: PackageMetadata) -> list[str]:
    """Last part of every ``License ::`` trove classifier, without approval markers."""
    leaves = []
    for c in meta.get_all("Classifier") or []:
        parts = [p.strip() for p in c.split("::")]
        if parts[0] == "License" and len(parts) > 1 and _key(parts[-1]) not in _CLASSIFIER_MARKERS:
            leaves.append(parts[-1])
    return leaves


def _segment_is_denied(segment: str) -> bool:
    if _OTHER_DENIED_TEXT.search(segment):
        return True
    for m in _GPL_TEXT.finditer(segment):
        before = re.findall(r"[a-z]+", segment[: m.start()].casefold())[-3:]
        if not _LESSER_WORDS.intersection(before):
            return True
    return False


def mentions_denied(meta: PackageMetadata) -> bool:
    """True when a licence field or classifier names GPL, AGPL, SSPL, BSL/BUSL or RSAL.

    Checks ``License-Expression``, ``License`` (any length) and each licence
    classifier leaf, one segment at a time. A GPL match preceded within three words by
    "Lesser" or "Library" is skipped, because that is the LGPL wording.
    """
    texts = [_first(meta, "License-Expression"), _first(meta, "License"), *classifier_leaves(meta)]
    return any(_segment_is_denied(seg) for t in texts if t for seg in _SEGMENT_SPLIT.split(t))


@dataclass
class Result:
    name: str
    version: str
    licence: str
    source: str
    category: Category
    status: Status
    note: str = ""


def evaluate(name: str, version: str, meta: PackageMetadata, policy: Policy) -> Result:
    """Classify one distribution from the first licence field that is present.

    A present field the gate cannot map gives ``unknown``. A lower-priority field is
    never used to override it.
    """
    candidates = licence_candidates(meta)
    licence, source = "(no licence metadata)", "-"
    category: Category = "unknown"
    if candidates:
        source, licence = candidates[0]
        category = classify(licence, policy, spdx=source == "License-Expression")

    cname = canonical_name(name)
    note = ""
    status: Status
    if category == "allowed":
        status = "pass"
    elif category == "conditional":
        status = "warn"
        note = "LGPL: allowed only as an unmodified library (plan section 9)"
    elif category == "denied_in_process":
        status = "fail"
        note = "not allowed in-process (plan section 9)"
        if cname in policy.exceptions:
            note += "; exception ignored for denied licences"
    elif cname in policy.exceptions and mentions_denied(meta):
        status = "fail"
        note = "metadata text names GPL, AGPL, SSPL, BSL or RSAL; exception ignored (plan section 9)"
    elif cname in policy.exceptions:
        status = "exception"
        note = policy.exceptions[cname]
    else:
        status = "fail"
        note = "licence not recognised or not approved; fix metadata mapping or add an exception"
    return Result(name, version, licence, source, category, status, note)


def workspace_names(root: Path = REPO_ROOT) -> frozenset[str]:
    """Exact names of the workspace's own packages.

    Read from ``[tool.uv.workspace] members`` in the root ``pyproject.toml`` and the
    ``[project] name`` of each member. Returns an empty set when the root file is
    missing, so nothing is skipped.
    """
    root_file = root / "pyproject.toml"
    if not root_file.is_file():
        return frozenset()
    with root_file.open("rb") as fh:
        members = tomllib.load(fh).get("tool", {}).get("uv", {}).get("workspace", {}).get("members", [])
    names: set[str] = set()
    for pattern in members:
        for member in sorted(root.glob(pattern)):
            member_file = member / "pyproject.toml"
            if not member_file.is_file():
                continue
            with member_file.open("rb") as fh:
                name = tomllib.load(fh).get("project", {}).get("name")
            if name:
                names.add(canonical_name(str(name)))
    return frozenset(names)


def installed(exclude: frozenset[str] = frozenset()) -> Iterator[tuple[str, str, PackageMetadata]]:
    """Installed distributions, de-duplicated, without the names in ``exclude``.

    ``exclude`` holds PEP 503 names and is matched exactly, never by prefix.
    """
    seen: set[str] = set()
    for dist in distributions():
        name = _first(dist.metadata, "Name")
        if not name:
            continue
        cname = canonical_name(name)
        if cname in seen or cname in exclude:
            continue
        seen.add(cname)
        yield name, dist.version, dist.metadata


def check(dists: Iterable[tuple[str, str, PackageMetadata]], policy: Policy) -> list[Result]:
    results = [evaluate(n, v, m, policy) for n, v, m in dists]
    return sorted(results, key=lambda r: canonical_name(r.name))


def gate_passes(results: Iterable[Result]) -> bool:
    return all(r.status != "fail" for r in results)


def format_table(results: list[Result]) -> str:
    headers = ("Distribution", "Version", "Licence", "Source", "Category", "Result")
    rows = [(r.name, r.version, r.licence, r.source, r.category, r.status.upper()) for r in results]
    widths = [max(len(h), *(len(row[i]) for row in rows)) if rows else len(h) for i, h in enumerate(headers)]
    lines = ["  ".join(h.ljust(w) for h, w in zip(headers, widths, strict=True))]
    lines.append("  ".join("-" * w for w in widths))
    lines += ["  ".join(c.ljust(w) for c, w in zip(row, widths, strict=True)) for row in rows]
    notes = [f"  {r.name}: {r.note}" for r in results if r.status != "pass" and r.note]
    if notes:
        lines += ["", "Notes:", *notes]
    return "\n".join(lines)


def default_repo_root() -> Path:
    """The source checkout for an editable install, else the current directory.

    A wheel install inside a service image has no checkout next to it. Run the gate
    from a repo checkout, or pass ``--repo-root`` (and ``--policy`` if needed).
    """
    return REPO_ROOT if (REPO_ROOT / POLICY_RELPATH).is_file() else Path.cwd()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="edp_ci.license_gate", description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="repo checkout; its pyproject.toml names the workspace packages to skip",
    )
    parser.add_argument("--policy", type=Path, default=None, help="policy TOML file")
    parser.add_argument("--json", action="store_true", help="print results as JSON")
    args = parser.parse_args(argv)

    root: Path = args.repo_root or default_repo_root()
    args.policy = args.policy or root / POLICY_RELPATH
    if not args.policy.is_file():
        print(f"Policy file not found: {args.policy}. Pass --policy or --repo-root.", file=sys.stderr)
        return 2

    policy = load_policy(args.policy)
    results = check(installed(workspace_names(root)), policy)
    ok = gate_passes(results)
    counts = {s: sum(r.status == s for r in results) for s in ("pass", "warn", "exception", "fail")}

    if args.json:
        print(json.dumps({"ok": ok, "counts": counts, "results": [asdict(r) for r in results]}, indent=2))
    else:
        print(f"Licence gate (plan section 9). Policy: {args.policy}")
        print(format_table(results))
        print()
        summary = ", ".join(f"{v} {k}" for k, v in counts.items())
        print(f"{len(results)} distributions checked: {summary}. Gate {'PASSED' if ok else 'FAILED'}.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

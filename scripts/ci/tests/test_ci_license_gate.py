"""Tests for the CI licence gate (plan section 9).

All tests use synthetic metadata except the last one, which runs the gate on the
real environment.
"""

import subprocess
import sys
from collections.abc import Iterator
from email.message import Message
from pathlib import Path
from types import SimpleNamespace

import pytest

from edp_ci import license_gate
from edp_ci.license_gate import (
    DEFAULT_POLICY,
    POLICY_RELPATH,
    Policy,
    check,
    classify,
    default_repo_root,
    evaluate,
    gate_passes,
    installed,
    licence_candidates,
    load_policy,
    main,
    mentions_denied,
    normalise,
    workspace_names,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def policy() -> Policy:
    return load_policy(DEFAULT_POLICY)


def meta(
    expression: str | None = None, licence: str | None = None, classifiers: tuple[str, ...] = ()
) -> Message:
    """Synthetic core metadata, the same shape importlib.metadata returns."""
    m = Message()
    if expression is not None:
        m["License-Expression"] = expression
    if licence is not None:
        m["License"] = licence
    for c in classifiers:
        m["Classifier"] = c
    return m


# --- normalisation --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("MIT", "MIT"),
        ("MIT License", "MIT"),
        ("Apache 2.0", "Apache-2.0"),
        ("apache-2.0", "Apache-2.0"),
        ("BSD License", "BSD"),
        ("BSD 3-Clause", "BSD-3-Clause"),
        ("Mozilla Public License 2.0 (MPL 2.0)", "MPL-2.0"),
        ("GPL-3.0", "GPL-3.0-only"),
        ("GPL-2.0+", "GPL-2.0-or-later"),
        ("GNU Affero General Public License v3", "AGPL-3.0-only"),
        ("GNU Lesser General Public License v3 (LGPLv3)", "LGPL-3.0-only"),
        ("GNU Library or Lesser General Public License (LGPL)", "LGPL"),
        ("Business Source License", "BUSL"),
        ("BSL", "BUSL"),
        ("Business Source License 1.0", "BUSL-1.0"),
        ("BSL 1.1", "BUSL-1.1"),
        ("SSPL", "SSPL"),
        ("SSPL v1", "SSPL-1.0"),
        ("Redis Source Available License", "RSAL"),
        ("Redis Source Available License 2.0 (RSALv2)", "RSAL"),
        ("GPL-1.0", "GPL-1.0-only"),
    ],
)
def test_normalise_known_names(text: str, expected: str) -> None:
    assert normalise(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Apache Software License",
        "Python Software Foundation License",
        "Other/Proprietary License",
        "BSL 1.0",
        "UNKNOWN",
        "",
    ],
)
def test_normalise_leaves_ambiguous_names_unknown(text: str) -> None:
    assert normalise(text) is None


# --- classification -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("expr", "expected"),
    [
        ("MIT", "allowed"),
        ("Apache-2.0", "allowed"),
        ("AGPL-3.0-only", "denied_in_process"),
        ("AGPL-3.0-or-later", "denied_in_process"),
        ("GPL-2.0-only", "denied_in_process"),
        ("SSPL-1.0", "denied_in_process"),
        ("SSPL", "denied_in_process"),
        ("BUSL", "denied_in_process"),
        ("RSAL", "denied_in_process"),
        ("BUSL-1.0", "denied_in_process"),
        ("GPL-1.0-or-later", "denied_in_process"),
        ("LGPL-2.1-only", "conditional"),
        ("MIT OR GPL-3.0", "allowed"),
        ("MIT AND AGPL-3.0", "denied_in_process"),
        ("MIT AND LGPL-3.0-or-later", "conditional"),
        ("LGPL-2.1-only OR GPL-2.0-only", "conditional"),
        ("(MIT OR GPL-3.0-only) AND BSD-3-Clause", "allowed"),
        # WITH: only a known SPDX exception id is accepted. An unknown one gives
        # unknown, or keeps a denied left-hand side denied.
        ("LGPL-2.1-only WITH OCCT-exception-1.0", "conditional"),
        ("Apache-2.0 WITH Commons-Clause", "unknown"),
        ("GPL-2.0-only WITH Classpath-exception-2.0", "denied_in_process"),
        ("MIT WITH", "unknown"),
        ("mit or apache-2.0", "allowed"),
        ("Some-Custom-Licence", "unknown"),
        ("MIT AND Some-Custom-Licence", "unknown"),
        ("MIT OR", "unknown"),
        ("", "unknown"),
    ],
)
def test_classify(expr: str, expected: str, policy: Policy) -> None:
    assert classify(expr, policy) == expected


# --- reading metadata -----------------------------------------------------------------


def test_with_in_free_text_is_unknown(policy: Policy) -> None:
    """Commons Clause adds restrictions; it is not an SPDX exception (plan section 9)."""
    assert classify("Apache 2.0 with Commons Clause", policy, spdx=False) == "unknown"
    r = evaluate("pkg", "1.0", meta(licence="Apache 2.0 with Commons Clause"), policy)
    assert (r.source, r.category, r.status) == ("License", "unknown", "fail")


def test_with_known_exception_in_license_expression(policy: Policy) -> None:
    r = evaluate("pkg", "1.0", meta("LGPL-2.1-only WITH OCCT-exception-1.0"), policy)
    assert (r.category, r.status) == ("conditional", "warn")
    r = evaluate("pkg", "1.0", meta("Apache-2.0 WITH LLVM-exception"), policy)
    assert (r.category, r.status) == ("unknown", "fail")


@pytest.mark.parametrize("placeholder", ["UNKNOWN", "unknown", ""])
def test_unknown_license_placeholder_is_treated_as_absent(placeholder: str, policy: Policy) -> None:
    m = meta(licence=placeholder, classifiers=("License :: OSI Approved :: MIT License",))
    r = evaluate("pkg", "1.0", m, policy)
    assert (r.source, r.licence, r.status) == ("Classifier", "MIT", "pass")


def test_license_expression_wins_over_other_fields(policy: Policy) -> None:
    m = meta("MIT", "GPL", ("License :: OSI Approved :: GNU General Public License (GPL)",))
    assert licence_candidates(m)[0] == ("License-Expression", "MIT")
    assert evaluate("pkg", "1.0", m, policy).category == "allowed"


def test_long_license_text_is_skipped_for_classifiers(policy: Policy) -> None:
    long_text = "Permission is hereby granted...\n" * 20
    m = meta(licence=long_text, classifiers=("License :: OSI Approved :: MIT License",))
    r = evaluate("pkg", "1.0", m, policy)
    assert (r.source, r.licence, r.status) == ("Classifier", "MIT", "pass")


def test_osi_approved_marker_alone_is_unknown(policy: Policy) -> None:
    r = evaluate("pkg", "1.0", meta(classifiers=("License :: OSI Approved",)), policy)
    assert r.category == "unknown"
    assert r.status == "fail"


def test_several_classifiers_are_combined_with_and(policy: Policy) -> None:
    m = meta(
        classifiers=(
            "License :: OSI Approved :: MIT License",
            "License :: OSI Approved :: GNU Affero General Public License v3",
        )
    )
    assert evaluate("pkg", "1.0", m, policy).category == "denied_in_process"


def test_agpl_classifier_with_unmappable_classifier_is_denied(policy: Policy) -> None:
    """Dual AGPL or commercial packages (plan section 9 watch-list) stay denied."""
    m = meta(
        classifiers=(
            "License :: OSI Approved :: GNU Affero General Public License v3",
            "License :: Other/Proprietary License",
        )
    )
    p = Policy(policy.allowed, policy.conditional, policy.denied_in_process, {"pkg": "should not help"})
    r = evaluate("pkg", "1.0", m, p)
    assert (r.category, r.status) == ("denied_in_process", "fail")


def test_unmappable_classifier_alone_is_unknown(policy: Policy) -> None:
    m = meta(classifiers=("License :: OSI Approved :: MIT License", "License :: Other/Proprietary License"))
    assert evaluate("pkg", "1.0", m, policy).category == "unknown"


def test_classifier_leaf_with_operator_words_stays_unknown(policy: Policy) -> None:
    m = meta(classifiers=("License :: Dual MIT or commercial (see file)",))
    assert evaluate("pkg", "1.0", m, policy).category == "unknown"


def test_psf_classifier_stays_unknown(policy: Policy) -> None:
    """PSF-2.0 is accepted only by id; the unversioned classifier is not mapped."""
    m = meta(classifiers=("License :: OSI Approved :: Python Software Foundation License",))
    assert evaluate("pkg", "1.0", m, policy).category == "unknown"
    assert evaluate("pkg", "1.0", meta("PSF-2.0"), policy).category == "allowed"


@pytest.mark.parametrize(
    ("expression", "licence"),
    [
        ("AGPL-3.0-only OR LicenseRef-Commercial", None),
        ("LicenseRef-Proprietary", None),
        (None, "GPL v3"),
        (None, "Custom terms"),
    ],
)
def test_unmappable_first_field_is_not_overridden_by_classifier(
    expression: str | None, licence: str | None, policy: Policy
) -> None:
    m = meta(expression, licence, ("License :: OSI Approved :: MIT License",))
    r = evaluate("pkg", "1.0", m, policy)
    assert r.source == ("License-Expression" if expression else "License")
    assert (r.category, r.status) == ("unknown", "fail")


# --- gate decisions -------------------------------------------------------------------


def test_agpl_distribution_fails_the_gate(policy: Policy) -> None:
    """Phase 0 exit criterion: CI blocks any AGPL dependency imported in-process."""
    results = check([("good", "1", meta("MIT")), ("bad", "1", meta("AGPL-3.0-only"))], policy)
    assert not gate_passes(results)
    assert {r.name: r.status for r in results} == {"bad": "fail", "good": "pass"}


def test_lgpl_warns_but_passes(policy: Policy) -> None:
    results = check([("lib", "1", meta("LGPL-2.1-or-later"))], policy)
    assert results[0].status == "warn"
    assert gate_passes(results)


def test_unknown_licence_fails(policy: Policy) -> None:
    results = check([("odd", "1", meta(licence="Custom terms"))], policy)
    assert results[0].category == "unknown"
    assert not gate_passes(results)


def test_exception_list_honoured_for_unknown(policy: Policy) -> None:
    p = Policy(policy.allowed, policy.conditional, policy.denied_in_process, {"odd-pkg": "metadata says X"})
    results = check([("Odd_Pkg", "1", meta(licence="Custom terms"))], p)
    assert results[0].status == "exception"
    assert results[0].note == "metadata says X"
    assert gate_passes(results)


def test_exception_does_not_clear_denied_licence(policy: Policy) -> None:
    p = Policy(policy.allowed, policy.conditional, policy.denied_in_process, {"bad": "should not help"})
    results = check([("bad", "1", meta("AGPL-3.0-only"))], p)
    assert results[0].status == "fail"
    assert not gate_passes(results)


@pytest.mark.parametrize(
    "licence",
    [
        "AGPL v3",
        "GNU AGPLv3",
        "GPLv3 or later",
        "Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License",
        "GNU General Public License, version 3",
        # "Lesser" in one segment must not hide AGPL in another.
        "GNU Lesser GPL or GNU AGPL",
        "GNU Lesser GPL & GNU AGPL",
        "Library GPL v2 - AGPL",
        "GNU LGPL + GNU GPL v3",
        # SSPL, BSL and RSAL text the alias table cannot map (plan section 9 watch-list).
        "Server Side Public License, v 1",
        "SSPL version 2",
        "Business Source License, version 1.1",
        "BSL (see LICENSE)",
        "Redis Source Available License v2",
    ],
)
def test_exception_does_not_clear_unmapped_denied_text(licence: str, policy: Policy) -> None:
    p = Policy(policy.allowed, policy.conditional, policy.denied_in_process, {"pkg": "should not help"})
    m = meta(licence=licence)
    assert mentions_denied(m)
    r = evaluate("pkg", "1.0", m, p)
    assert (r.category, r.status) == ("unknown", "fail")


@pytest.mark.parametrize(
    "licence",
    [
        "GNU Lesser General Public License, custom wording",
        "GNU Library GPL, custom wording",
        "LGPLv2.1 custom",
        "GNU Library or Lesser General Public License (LGPL)",
        "Boost Software License 1.0 (BSL-1.0)",
        "Universal custom licence",
        "Custom",
    ],
)
def test_lgpl_or_other_text_does_not_trigger_denied_check(licence: str) -> None:
    assert not mentions_denied(meta(licence=licence))


# --- workspace packages ---------------------------------------------------------------


def test_workspace_names_are_read_from_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.uv.workspace]\nmembers = ["a", "pkgs/*"]\n', encoding="utf-8"
    )
    for sub, name in (("a", "Edp_Contracts"), ("pkgs/b", "edp-ci")):
        (tmp_path / sub).mkdir(parents=True)
        (tmp_path / sub / "pyproject.toml").write_text(f'[project]\nname = "{name}"\n', encoding="utf-8")
    assert workspace_names(tmp_path) == {"edp-contracts", "edp-ci"}
    assert workspace_names(tmp_path / "missing") == frozenset()


def test_installed_excludes_exact_names_only(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(name: str) -> SimpleNamespace:
        m = meta("MIT")
        m["Name"] = name
        return SimpleNamespace(metadata=m, version="1")

    dists = [fake("edp-ci"), fake("edp-thirdparty"), fake("other")]
    monkeypatch.setattr(license_gate, "distributions", lambda: dists)
    assert [n for n, _, _ in installed(frozenset({"edp-ci"}))] == ["edp-thirdparty", "other"]


# --- command line ---------------------------------------------------------------------


def test_cli_returns_one_for_failing_policy(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_installed(exclude: frozenset[str] = frozenset()) -> Iterator[tuple[str, str, Message]]:
        yield "good", "1", meta("MIT")
        yield "bad", "1", meta("AGPL-3.0-only")

    monkeypatch.setattr(license_gate, "installed", fake_installed)
    assert main(["--json"]) == 1
    assert '"ok": false' in capsys.readouterr().out
    # An empty policy approves nothing, so even the MIT distribution fails.
    empty = tmp_path / "empty.toml"
    empty.write_text("[allowed]\nids = []\n", encoding="utf-8")
    assert main(["--policy", str(empty)]) == 1
    assert "0 pass" in capsys.readouterr().out


def test_cli_returns_zero_for_passing_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_installed(exclude: frozenset[str] = frozenset()) -> Iterator[tuple[str, str, Message]]:
        yield "good", "1", meta("MIT")
        yield "lib", "1", meta("LGPL-2.1-only")

    monkeypatch.setattr(license_gate, "installed", fake_installed)
    assert main([]) == 0


def test_cli_reads_workspace_and_policy_from_repo_root(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """--repo-root sets both the policy path and the workspace names to skip."""
    seen: list[frozenset[str]] = []

    def fake_installed(exclude: frozenset[str] = frozenset()) -> Iterator[tuple[str, str, Message]]:
        seen.append(exclude)
        yield "good", "1", meta("MIT")

    monkeypatch.setattr(license_gate, "installed", fake_installed)
    (tmp_path / "pyproject.toml").write_text('[tool.uv.workspace]\nmembers = ["svc"]\n', encoding="utf-8")
    (tmp_path / "svc").mkdir()
    (tmp_path / "svc" / "pyproject.toml").write_text('[project]\nname = "edp-svc"\n', encoding="utf-8")
    (tmp_path / POLICY_RELPATH).parent.mkdir(parents=True)
    (tmp_path / POLICY_RELPATH).write_text('[allowed]\nids = ["MIT"]\n', encoding="utf-8")
    assert main(["--repo-root", str(tmp_path)]) == 0
    assert seen == [frozenset({"edp-svc"})]
    capsys.readouterr()
    # No policy file under the given root: exit 2, nothing is checked.
    assert main(["--repo-root", str(tmp_path / "svc")]) == 2
    assert "Policy file not found" in capsys.readouterr().err


def test_default_repo_root_is_this_checkout() -> None:
    assert default_repo_root() == REPO_ROOT
    assert DEFAULT_POLICY == REPO_ROOT / POLICY_RELPATH


# --- integration ----------------------------------------------------------------------


def test_gate_passes_on_this_environment() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "edp_ci.license_gate"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

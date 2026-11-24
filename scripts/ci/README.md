# scripts/ci: provider-neutral CI checks

Phase 0 task 5 asks for "CI (lint, type check, tests, license scan, SBOM)" (plan §6, Phase 0). Phase 0 task 6 asks for the licence policy (plan §9). The Phase 0 exit criterion is "CI blocks any AGPL dependency imported in-process".

**The CI provider is not decided (OD-18).** The folder is not a git repository yet. The steps live in a plain bash script so that any provider can call it.

## Files

| File | Purpose |
|---|---|
| `run_ci.sh` | Runs every step below from the repo root. Stops at the first failing step (`set -euo pipefail`) |
| `license_policy.toml` | Machine-readable licence policy: `allowed`, `conditional`, `denied_in_process`, `exceptions` |
| `src/edp_ci/license_gate.py` | The licence gate. Standard library only |
| `tests/test_ci_license_gate.py` | Unit tests with synthetic metadata (the CLI tests replace `installed()`), plus one test that runs the gate on the real environment |
| [`docs/policies/license-policy.md`](../../docs/policies/license-policy.md) | The policy in prose, the plan §9 watch-list, and what the gate does not cover |

## Steps in `run_ci.sh`

| # | Step | Command | Fails the run when |
|---|---|---|---|
| 1 | Lint | `uv run ruff check .` | Any ruff finding (rules set in the root `pyproject.toml`) |
| 2 | Type check | `uv run mypy contracts/src eval/src scripts/ci/src` | Any mypy error |
| 3 | Tests | `uv run pytest` | Any failing test in the `testpaths` of the root `pyproject.toml` |
| 4 | Licence gate | `uv run python -m edp_ci.license_gate --repo-root .` | Any installed distribution is `denied_in_process`, or `unknown` and not in `[exceptions]`. Exit 2 if the policy file is not found |
| 5 | SBOM | `syft dir:. -o cyclonedx-json=build/sbom.cdx.json` | Syft errors. If `syft` is not installed, prints `SKIPPED` and continues |
| 6 | Licence scan | `scancode --version` only | If `scancode` is not installed, prints `SKIPPED` and continues. The scan command itself is TBD in Phase 0 (plan Phase 0 task 6) |

Syft and ScanCode Toolkit are the plan's supply-chain tools, with Trivy (plan §4.3). None of the three is installed on the current development machine. Trivy is not wired into the script: plan Phase 0 task 5 does not list a vulnerability scan. Deck slide 62 mentions "lint, type, license and vulnerability checks". Wiring Trivy is an open item.

Not in the script yet, although Phase 0 task 5 lists them: container build (Rancher Desktop chosen but not installed yet, OD-21) and the dev Kubernetes cluster.

## Running

```bash
cd D:/Construction-Diagram/Engineering-Diagram
bash scripts/ci/run_ci.sh

# only the licence gate
uv run python -m edp_ci.license_gate                 # table, exit 1 on failure
uv run python -m edp_ci.license_gate --json          # machine-readable
uv run python -m edp_ci.license_gate --policy other.toml
uv run python -m edp_ci.license_gate --repo-root PATH   # checkout with pyproject.toml and scripts/ci/license_policy.toml
uv run pytest scripts/ci/tests
```

## How the licence gate decides

1. It lists every distribution installed in the Python environment it runs in. It skips the workspace's own packages by exact name. The names come from `[tool.uv.workspace] members` in the root `pyproject.toml` and the `[project] name` of each member. There is no prefix match. The repo root is the checkout the gate is installed from (editable install). If that checkout is not found, the current directory is used. `--repo-root` sets it explicitly. The default policy file is `scripts/ci/license_policy.toml` under that root. If the policy file is missing, the gate exits 2. A run outside a repo checkout (for example a wheel install in a service image) therefore needs `--repo-root` or `--policy`.
2. It reads the licence from the metadata, in this order: `License-Expression`, then `License` if it is short (one line, at most 100 characters), then the `License :: ...` trove classifiers. The first field that is present is used. A `License` value that is empty or exactly `UNKNOWN` (any case) counts as absent: older setuptools writes `UNKNOWN` when no licence is set. If the field used cannot be mapped, the result is `unknown`; a later field never overrides it. All licence classifiers are joined with AND. A classifier the gate cannot map stays in the expression as an unknown term, so an AGPL or GPL classifier still makes the result `denied_in_process`.
3. It maps the text to an SPDX-like id through a small table in `license_gate.py`. Names whose version is not stated are left unknown, unless the policy has an unversioned id for them (`BSD`, `LGPL`, `GPL`, `AGPL`, `SSPL`, `BUSL`, `RSAL`). Versioned RSAL text (for example "RSALv2") and LGPL v2 text that does not say 2.0 or 2.1 also map to unversioned ids, because the policy has no matching versioned id. "BSL 1.0" is not mapped, because `BSL-1.0` is the SPDX id of the Boost Software License. For example, the classifiers "Apache Software License" and "Python Software Foundation License" without a version stay unknown, because plan §9 names Apache 2.0 only and `PSF-2.0` is a proposed addition. This split with "BSD License" is an open item in the policy document.
4. It classifies the result. `A OR B` passes if any option is allowed. `A AND B` takes the worse of the two. `X WITH E` is read only in a `License-Expression`, and is classified as `X` only when `E` is in the known SPDX exception list in `license_gate.py` (`OCCT-exception-1.0` at the time of writing). Any other `E` gives `unknown`, or keeps `X` denied if `X` is denied. In the free-text `License` field, "with" makes the result `unknown`; for example "Apache 2.0 with Commons Clause" fails.
5. For an `unknown` result listed in `[exceptions]`, it first checks the raw metadata text, one segment at a time (split on and/or/with, commas, slashes, semicolons and brackets). The exception is ignored and the result fails when a segment names GPL, AGPL, Affero or "General Public License" without "Lesser" or "Library" in the same segment, or names SSPL, BSL, BUSL, "Business Source License" or RSAL.

| Category | Result | Exit code |
|---|---|---|
| `allowed` | PASS | 0 |
| `conditional` (LGPL) | WARN, passes. "Without modification" is a review item; the gate cannot check it | 0 |
| `unknown`, listed in `[exceptions]`, no GPL/AGPL/SSPL/BSL/RSAL text | EXCEPTION, passes, reason printed | 0 |
| `unknown`, listed in `[exceptions]`, GPL/AGPL/SSPL/BSL/RSAL text in metadata | FAIL. The exception is ignored | 1 |
| `unknown`, not listed | FAIL | 1 |
| `denied_in_process` (GPL, AGPL, SSPL, RSAL, BUSL) | FAIL. An `[exceptions]` entry does not change this | 1 |

## Adding an exception

Only for a distribution whose metadata the gate cannot map. Check what the metadata says first:

```bash
uv run python -c "import importlib.metadata as m; d=m.metadata('NAME'); print(d.get_all('Classifier'), d.get('License'), d.get('License-Expression'))"
```

Then add `"name" = "reason quoting the metadata"` under `[exceptions]` in `license_policy.toml`. Prefer extending the mapping table when the text is a plain licence name. Never add GPL, AGPL, SSPL, BSL/BUSL or RSAL packages. The text check in step 5 is a text match only, so it does not replace reading the metadata.

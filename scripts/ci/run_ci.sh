#!/usr/bin/env bash
# Provider-neutral CI steps for Phase 0 task 5 (plan section 6, Phase 0):
# lint, type check, tests, licence scan, SBOM.
# The CI provider is not decided (OD-18); any provider can call this script.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."

step() { printf '\n=== %s ===\n' "$1"; }

step "Lint (ruff)"
uv run ruff check .

step "Type check (mypy)"
uv run mypy contracts/src eval/src scripts/ci/src platform/kit/src platform/fabric/src platform/catalogue/src platform/gateway/src orchestrator/src blocks/b1_parser/src blocks/b2_interpretation/src blocks/b3_knowledge_graph/src blocks/b4_generation/src blocks/b5_opencad/src blocks/b6_solvers/src blocks/b8_report/src

step "Tests (pytest)"
uv run pytest

step "Requirements files in sync with uv.lock (OD-18)"
# requirements.txt / requirements-dev.txt are generated from uv.lock for pip users.
# Regenerate with the two "uv export" commands in CLAUDE.md if this step fails.
diff <(uv export --format requirements.txt --no-dev --no-hashes --frozen | grep -v '^#') \
     <(tr -d '\r' < requirements.txt | grep -v '^#') >/dev/null \
  && diff <(uv export --format requirements.txt --no-hashes --frozen | grep -v '^#') \
          <(tr -d '\r' < requirements-dev.txt | grep -v '^#') >/dev/null \
  && echo "requirements.txt and requirements-dev.txt match uv.lock" \
  || { echo "FAILED: requirements files are out of date; regenerate them (see CLAUDE.md)"; exit 1; }

step "Licence gate (plan section 9)"
uv run python -m edp_ci.license_gate --repo-root .

step "Console: npm licence gate and type check (plan §9, §4.3)"
if command -v node >/dev/null 2>&1 && [ -d console/node_modules ]; then
    (cd console && npm run --silent licences && npm run --silent typecheck && echo "console type check passed")
else
    echo "SKIPPED: run 'npm install' in console/ first (needs Node.js; registry in console/.npmrc)"
fi

step "SBOM (Syft)"
if command -v syft >/dev/null 2>&1; then
    mkdir -p build
    syft dir:. -o cyclonedx-json=build/sbom.cdx.json
    echo "SBOM written to build/sbom.cdx.json"
else
    echo "SKIPPED: syft not installed (plan §4.3 Supply chain: Trivy, Syft, ScanCode Toolkit)"
fi

step "Licence scan (ScanCode Toolkit)"
if command -v scancode >/dev/null 2>&1; then
    scancode --version
    # Scan options and targets are not set yet: Phase 0 task 6 "run the first ScanCode
    # scan on the candidate stack" (plan section 6). TBD in Phase 0.
    echo "ScanCode found; scan command TBD in Phase 0 (plan Phase 0 task 6)"
else
    echo "SKIPPED: scancode not installed (plan §4.3 Supply chain: Trivy, Syft, ScanCode Toolkit)"
fi

step "Done"

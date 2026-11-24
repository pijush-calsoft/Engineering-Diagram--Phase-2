# AI-Powered Engineering Diagram Platform (EDP)

This platform turns engineering inputs (2D drawings, 3D models, requirements, material cards, load cases, solver runs and, later, sensor signals) into editable CAD models, validated exports, margin reports, insight reports and a complete audit trail (plan §1).

> Status: **Phase 0 (Discovery, golden data and foundations), in progress.** See [docs/progress/PROGRESS.md](docs/progress/PROGRESS.md).

## Read first

| Document | What it is |
|---|---|
| [engineering-diagram-platform-plan.md](engineering-diagram-platform-plan.md) | The baseline delivery plan |
| [docs/README.md](docs/README.md) | Index of all project documentation |
| [docs/progress/PROGRESS.md](docs/progress/PROGRESS.md) | Phase tracker and session log |
| [docs/open-decisions.md](docs/open-decisions.md) | Decisions waiting on an owner |
| [CLAUDE.md](CLAUDE.md) | Working rules for AI-assisted sessions in this repo |

## Quick start

Requires Python 3.11 or newer and [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env          # then add OPENAI_API_KEY (never commit .env)
uv sync                       # or: pip install -r requirements-dev.txt
uv run pytest
bash scripts/ci/run_ci.sh
```

`requirements.txt` (runtime) and `requirements-dev.txt` (with test and lint tools) are generated from `uv.lock`. CI fails if they drift.

## Layout

The layout follows plan Appendix A. See [CLAUDE.md](CLAUDE.md#layout-plan-appendix-a) for what each directory holds and which phase fills it.

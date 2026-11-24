# CLAUDE.md: working harness for this repository

The AI-Powered Engineering Diagram Platform (EDP) monorepo. Read this first in every session.

## Start of every session

1. Read [docs/progress/PROGRESS.md](docs/progress/PROGRESS.md). It shows where the project stands, phase by phase.
2. Read [docs/open-decisions.md](docs/open-decisions.md) before building anything those decisions touch.
3. For the phase you are working on, read that phase in the plan, `engineering-diagram-platform-plan.md` §6.

## Sources of truth

| Source | Role |
|---|---|
| `engineering-diagram-platform-plan.md` (repo root) | **Baseline plan.** Phases, stack, contract, exit criteria |
| `AI_Engineering_Diagram_Platform_2170_0615 (1).pptx` (repo root); text copy in [docs/reference/deck-text.md](docs/reference/deck-text.md) | Reference only |
| [docs/reference/plan-vs-deck.md](docs/reference/plan-vs-deck.md) | Where the two disagree. Follow the plan, and log the difference; never resolve one silently |

## Rules

- **Do not invent.** Every value, threshold, tool or licence in code or docs comes from the plan or deck, with a citation (plan §N / deck slide N). If neither gives it, write it as an open item in `docs/open-decisions.md`. Do not pick a default.
- **Source locators everywhere** (plan principle 1). No output item without a `SourceLocator`.
- **Contract first.** Blocks talk only through `edp_contracts` (plan §3). A breaking change needs a new major contract version.
- **Licence policy** (plan §9, [docs/policies/license-policy.md](docs/policies/license-policy.md)). Never import GPL, AGPL, SSPL or BSL code in-process. GPL tools run as separate processes or containers. `python -m edp_ci.license_gate` must pass.
- **Hosted model APIs only** (OD-5, ADR-0005): OpenAI (OD-37), including multimodal for vision and OCR (OD-38, ADR-0007); no local LLM, no fine-tuning. Keys live only in `.env` (git-ignored; template `.env.example`). Never print, commit or paste a key.
- **Client data stays out of the repo** (plan principle 7). No drawings, models or results in git, and no client names in code or docs.
- **No personal names** in docs. Use roles.
- Git commit messages carry no AI attribution (user's global instruction).

## Updating the docs (required at the end of every phase or work session)

1. Update the phase row and the task checklist in `docs/progress/PROGRESS.md`.
2. Add or append the phase log `docs/progress/phase-N.md`: what was done, files, how it was verified (commands and results), and what is still pending.
3. Add new open questions to `docs/open-decisions.md`; mark decided ones with the owner and date.
4. Add an ADR in `docs/adr/` for any architecture choice.

## Layout (plan Appendix A)

```
contracts/      edp-contracts: plug-in contract v0.1, artifact schemas, JSON Schema exports (contracts/schemas/)
platform/       fabric/, catalogue/, gateway/            (Phase 1, not started)
blocks/         b1_parser … b8_report, optimiser/ (R2), twin/ (R3)   (Phases 2 to 8, not started)
orchestrator/   LangGraph graphs, Temporal workflows     (Phase 1, not started; see OD-9)
console/        React app                                (Phase 1, not started)
mcp/            MCP server wrappers per block            (not started)
eval/           edp-eval: golden manifests, metrics, synthetic drawing generator (plan §7, OD-7)
deploy/         Helm, Argo CD, OpenTofu                  (not started; container runtime: Rancher Desktop, OD-21)
docs/           adr/, progress/, reference/, requirements/, policies/, setup/, open-decisions.md
scripts/ci/     edp-ci: provider-neutral CI steps and licence gate (not in Appendix A; added for Phase 0 task 5)
```

## Commands

Local setup (OD-2, runs locally): `cp .env.example .env`, then fill in `OPENAI_API_KEY` and the other values you have. Install with uv (`uv sync`) or pip (`pip install -r requirements-dev.txt`, run from the repo root).

```bash
uv sync                                   # install the workspace (Python >= 3.11; uv)
uv run pytest                             # all tests
uv run ruff check .                       # lint
uv run mypy contracts/src eval/src scripts/ci/src
uv run python -m edp_ci.license_gate      # licence policy gate
uv run python -m edp_contracts.export     # regenerate contracts/schemas/*.json
bash scripts/ci/run_ci.sh                 # everything CI runs
uv export --format requirements.txt --no-dev --no-hashes --frozen -o requirements.txt   # after any dependency change
uv export --format requirements.txt --no-hashes --frozen -o requirements-dev.txt
uv run python -m edp_eval.synth --out eval/golden/data/synthetic --count 80 --seed 2026 --uri-prefix s3://edp-fabric/golden/synthetic
```

Regenerate `contracts/schemas/` after any contract change, and commit the result with the change.

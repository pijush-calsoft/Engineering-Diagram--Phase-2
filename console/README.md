# Console

**Status: shell built** (plan Phase 1 "console shell"; parts of the Phase 6 console). React + Vite + TypeScript (plan §4.3), served by the local console API.

## Run it

```bash
# 1. Build the UI (needs Node.js; .npmrc points npm at a reachable registry, see below)
cd console
npm install
npm run build

# 2. Start the console API, which also serves the built UI
cd ..
uv run python -m edp_orchestrator.server --data-dir var/console --golden eval/golden/data/synthetic
# open http://127.0.0.1:8765
```

For UI development, run `npm run dev` in `console/` (Vite proxies `/api` to port 8765).

## What it shows

| Area | What it does | Source |
|---|---|---|
| Pipeline | Blocks 1 to 8 in run order, with live state from `run.block.*` events over SSE; stub blocks are marked | plan Phase 1 "pipeline map with live block status", §4.3 React Flow, SSE |
| Drawing sheet | The drawing redrawn from the parser's `geometry` output, with sheet zones; selecting a value traces its source entities in cyan; flagged entities in red | plan Phase 2 task 6, Phase 6 "select any item to highlight its source on the drawing" |
| Title block | Part number, revision, material, scale, units, tolerances read from the drawing, plus run, file version and status | |
| Inspector | Features and parameters from the design graph, with how each value was found and its sheet zone; flags; approve or reject when a run waits for review | plan Phase 3, principle 3, Phase 1 "interrupt points for human review" |
| Run events | The run's event log | plan Appendix B |

Links: `?run=<id>` opens a run; `&select=<id>` (for example `hole1.diameter`) opens it with that value traced.

Not built yet: the chat panel (needs the Model Gateway, OD-43), 3D viewer, script editor, margins and envelope views, report studio (Phases 4 to 6), Playwright tests (plan §4.3).

## Design

Drafting-office palette: vellum `#EEF1F0`, sheet `#FBFCFB`, ink `#1F2B33`, graphite `#66737C`, redline `#C62B35` for flags and review, trace cyan `#147A93` for selection. Type: Barlow Semi Condensed for headings and labels, Barlow for text, bundled locally with `@fontsource` so the console works offline (OD-2).

## Notes

- **npm registry.** `registry.npmjs.org` resets the connection on this network, so `console/.npmrc` uses `registry.yarnpkg.com`, which serves the same npm packages (OD-46).
- **Licences.** `npm run licences` checks every package in `package-lock.json` against plan §9. ISC, 0BSD and OFL-1.1 (fonts) are allowed pending sign-off (OD-31). CI runs it with the type check.
- **Narrow screens.** The layout stacks into one column below 44rem; checked at 500 px. Headless Edge cannot render narrower windows.

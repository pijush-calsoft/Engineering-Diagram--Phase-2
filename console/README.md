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
uv run python -m edp_orchestrator.server --data-dir var/console --golden eval/golden/data/synthetic eval/golden/data/synthetic-scan
# open http://127.0.0.1:8765
```

For UI development, run `npm run dev` in `console/` (Vite proxies `/api` to port 8765).

## What it shows

| Area | What it does | Source |
|---|---|---|
| Pipeline strip | Blocks 1 to 8 across the top in run order, live state from `run.block.*` events over SSE, a count of review flags per block; stub blocks are marked | plan Phase 1 "pipeline map with live block status", §4.3 React Flow, SSE |
| Runs | This session's runs, newest first, with file type, state and age; a click reopens a run (`GET /api/runs`) | plan Phase 6 console "files" |
| Drawing workspace | The parser's `geometry` redrawn as SVG with sheet zones. Drag to pan, wheel or + and - to zoom, Fit or 0 to reset. Layer switches with counts: geometry, dimensions, notes, features, flags, scan image, title block. Features from the design graph are drawn as markers (H1, S1, B1); a click traces the feature. The readout names the entity under the pointer. Dimension labels never shrink below a readable size on screen | plan Phase 2 task 6, Phase 6 "drawing workspace with per-agent layers", "select any item to highlight its source on the drawing" |
| Scans | The scanned image (`GET /api/runs/{id}/source`) under what the model read, each value in a box at the position it was read from | ADR-0007 locators |
| 3D viewer | STEP, IGES and STL models tessellated on the server (`GET /api/runs/{id}/mesh`, display only), drawn with three.js: orbit, zoom, pan, edges, hole axes with rings. Selecting a hole on the right highlights its faces by STEP entity id. Loaded only when a model is opened | plan Phase 6 console "3D viewer" |
| Title block | Part number, revision, material, scale, units, tolerances read from the drawing, plus run, file version and status; a switchable overlay | |
| Inspector | Features and parameters from the design graph, with how each value was found and its sheet zone; holes of 3D models; similar parts and corroboration; flags; approve or reject when a run waits for review | plan Phase 3, principle 3, Phase 1 "interrupt points for human review" |
| Ask about it (chat) | Tab beside "Read from the drawing". Questions about the open run are answered from numbered facts the platform read (title block, dimensions, notes, features, 3D solids, similar parts, flags); every answer lists the facts it used, and clicking one highlights its source on the drawing. Answers the facts do not support say so. Each answer shows tokens and cost; the panel shows total model spend. Built on assistant-ui (`useLocalRuntime` with an adapter that calls `POST /api/runs/{id}/chat`) | plan Phase 1 "Chat panel", §4.3 assistant-ui; Catalogue "cited answer" endpoint |
| Design check | Tab beside "Read from the drawing", for runs with a domain pack (construction samples `con-*`). The editable model's outline (each value marked "from drawing" or "changed"); the margin with peak stress, allowable, displacement, load case and mesh; the report's fact-check count, summary, all sections and a DOCX download (`GET /api/runs/{id}/report.docx`); one review box for any stop, which reads "Sign off" at the report. **Try another thickness** starts a new run of the same drawing with that thickness (`POST /api/runs/{id}/rerun`, `edp_kit.overrides`); the new run shows the earlier margin beside its own | deck slide 85 (Demo 4), plan Phase 6 console "margins" and "report studio" (first cut) |
| Generated model | A switch above the workspace: "Drawing" or "Generated model", the STEP block 5 built (`GET /api/runs/{id}/model`), with the peak-stress point from block 6 as a red dot | plan Phase 6 console "3D viewer" |
| Run events | A drawer at the bottom with the run's event log | plan Appendix B |

Links: `?run=<id>` opens a run; `&select=<id>` (for example `hole1.diameter`) opens it with that value traced.

Not built yet: run planning from chat (plan Phase 6 "Chat with run plans"), script editor, stress contour plot, envelope view, report versions and PDF (Phases 4 to 6). The design check covers margins and a first report view only.

## Design

Drafting-office palette: vellum `#EEF1F0`, sheet `#FBFCFB`, ink `#1F2B33`, graphite `#66737C`, redline `#C62B35` for flags and review, trace cyan `#147A93` for selection. Type: Barlow Semi Condensed for headings and labels, Barlow for text, bundled locally with `@fontsource` so the console works offline (OD-2).

## Tests

`npm run test:e2e` runs the Playwright tests in `e2e/` (plan §4.3) with the installed Microsoft Edge (no browser download). They start their own console API on port 8766 with freshly generated samples under `var/e2e/`, and mock chat answers in the browser, so they make no model calls. They cover: a DXF run through all eight blocks, feature markers and parameters tracing to the drawing, zoom and layer switches, the 3D viewer with hole highlighting, reopening a run from the list, chat citations, and a refused upload. They found one bug while being written: feature markers only took clicks on their outline (fixed).

## Notes

- **npm registry.** `registry.npmjs.org` resets the connection on this network, so `console/.npmrc` uses `registry.yarnpkg.com`, which serves the same npm packages (OD-46).
- **Licences.** `npm run licences` checks every package in `package-lock.json` against plan §9. ISC, 0BSD and OFL-1.1 (fonts) are allowed pending sign-off (OD-31). CI runs it with the type check.
- **Narrow screens.** The layout stacks into one column below 44rem; checked at 500 px. Headless Edge cannot render narrower windows.

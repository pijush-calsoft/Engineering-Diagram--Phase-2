# edp-contracts

Plug-in contract v0.1 and artifact schemas v0.1 (plan §3 and Phase 0 task 4).

| Module | Content | Source |
|---|---|---|
| `edp_contracts.block` | `SourceLocator`, `Artifact`, `Flag`, `BlockRequest`, `BlockResult`, `Block` protocol, `BlockContract` (body of `GET /contract`) | plan §3 (verbatim) |
| `edp_contracts.events` | Event subject names | plan §3, Appendix B |
| `edp_contracts.registry` | `discover_blocks()` over the `edp.blocks` entry point | plan §3 |
| `edp_contracts.artifacts.geometry` | Entities, views, units, scale, title block; locator required per entity | plan Phase 2 tasks 1, 3 |
| `edp_contracts.artifacts.design_graph` | Feature / parameter / tolerance / datum / material / requirement nodes and edges | plan Phase 3 task 1 |
| `edp_contracts.artifacts.cad_script` | CadQuery, build123d or OpenSCAD code plus parameter table; source required per parameter | plan Phase 4 tasks 1, 4, 5 |
| `edp_contracts.artifacts.margins` | Margin = allowable / computed, linked to solver run, load-case row and model version | plan Phase 5 task 4 and exit criteria |
| `edp_contracts.artifacts.report` | Sections and numeric claims that must resolve to the Run Store | plan Phase 6 tasks 1 to 3 |

Fields that the plan does not define yet are left as free-form `data` / `attributes` dicts. They get typed in a later schema version and are not guessed.

Not in v0.1, pending OD-15: the deck's `/status` and `/result` endpoints, plug-in manifest, `/v1` paths and deck event names (deck slides 38, 95).

Regenerate JSON Schemas after any change:

```bash
uv run python -m edp_contracts.export   # writes contracts/schemas/*.schema.json
```

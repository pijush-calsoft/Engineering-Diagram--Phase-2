# Block 4: Generation

**Status: first slice built (2026-11-26).** The template path for flat plates is built; the LLM path is not started. Package `edp_b4_generation`.

Turns a design graph into an editable CadQuery script whose parameters trace back to the drawing; template first, LLM second (plan Phase 4; deck slide 47 template zoo). Output: `cad_script` artifact.

| Built | Where |
|---|---|
| `plate` template: plates with through holes and one optional centred slot. Covers the generic `plate` family and the construction `base_plate` family | `edp_b4_generation.templates` |
| A named-parameter block at the top of every script; each parameter carries the source locator of its design-graph node (Phase 4 exit: 100 % parameters with locators) | `plan_plate`, `render_plate` |
| `NO_TEMPLATE` flag for a person when no template fits: brackets with a bend, several slots, missing outline size | `Generation.run` |
| Pass-through when the run names no domain pack ([ADR-0010](../../docs/adr/0010-domain-packs-and-pass-through.md)) | `edp_kit.passthrough` |

The template needs the plate's outline size. Block 2 now names the part-level dimensions that measure the whole outline (`role`: length, width, thickness); before this change it did not.

Not built:
- the sheet-metal template (brackets);
- OpenSCAD output;
- the LLM path through the Model Gateway, with its repair loop (plan Phase 4 tasks 2 and 3);
- the benchmark harness (deck F-22).

Planned stack (plan §4.2): CadQuery or build123d, OpenSCAD CLI. Code model through the Model Gateway (ADR-0005 replaces the plan's self-hosted Qwen-Coder).

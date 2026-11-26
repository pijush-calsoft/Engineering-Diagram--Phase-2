# ADR-0010: Domain packs, and pass-through for domain blocks

| | |
|---|---|
| Status | Proposed |
| Date | 2026-11-26 |
| Phase | Phases 4 to 6 (generation, solvers, report), first used for the construction slice (OD-55) |

## Context

Blocks 4 to 8 need inputs that belong to one component family, not to the platform: part templates, material cards, load cases, validation rules and report templates. The deck calls the container for these a domain pack: "A domain pack carries what is specific to seat, body, exhaust or turbomachinery": glossary, drawing templates, validation rules ("Load cases, standards and checks"), prompt library, benchmark golden set, optional domain model (deck slide 34), and report templates ("Part of each domain pack", deck slide 40). The deck's design spec names the pack per run: `domain: seat-structure  # from the domain packs` (deck slide 20).

The plan asks for "material cards and load cases as typed inputs (JSON, CSV)" (plan Phase 5 Solver task 2, as recorded in [acceptance-criteria.md](../requirements/acceptance-criteria.md) §6) and requires every margin to link to "the solver run, load case row and model version" (AC-P5-04).

The console and the CLI swap in every block registered through the `edp.blocks` entry point (`edp_orchestrator.server.Console`). Once blocks 4 to 8 are real, a run of a part with no matching pack (a generic bracket, an aluminium plate) would stop at block 4 or 6.

## Options considered

| Option | Source | Notes |
|---|---|---|
| A. A `domain_packs/<name>/` folder of versioned JSON files at the repo root; the run names its pack in `params["domain_pack"]`; blocks 4 to 8 pass a run with no pack through | deck slides 20, 34, 40 | Same shape as the deck's spec. The pass-through keeps runs of other families working, as the Phase 1 stubs did |
| B. Infer the pack from the drawing (for example from the material grade) | none | Hidden coupling: a material grade does not name a component family |
| C. Register the domain blocks only when an environment setting asks for them | none | Global, not per run; one console could not serve two families |

## Decision

Proposed: **Option A**.

- `domain_packs/construction/` holds `materials.json`, `load_cases.json` and a README. Files are identified by SHA-256. A margin's `load_case_row` locator carries the file hash and the case id (`edp_b6_solvers.packs`).
- A run names its pack: `params["domain_pack"]`. The CLI flag is `--domain-pack`. The console takes a `domain_pack` query parameter and gives samples named `con-*` the construction pack.
- `edp_kit.passthrough`: a domain block returns `ok` with placeholder outputs (`skipped://…`, carrying the inputs' source locators) when the run names no pack or an upstream block was skipped. Each skip is an `info` flag `SKIPPED`.
- Block 8 re-reads the pack files and stops with `PACK_CHANGED` if a hash differs from the one block 6 recorded, so a report never mixes pack versions.

## Consequences

- Runs of plates and brackets with no pack complete as before. The console tests now expect real blocks 4, 5, 6 and 8 and a stub block 7.
- New families are added as packs, not as code branches. The glossary, drawing templates, prompt library and golden set the deck lists are not in the construction pack yet.
- The pack is local files in Git. A pack registry, with access control and versions in the Data Catalogue, is not built (plan Phase 1 Data Catalogue; deck slide 39).

## Open items

- Whether the pack choice belongs in the run spec (`companion.design.yaml`, deck slide 20), which is not built: OD-60.
- Illustrative load values in the construction pack: OD-56.
- Who owns and signs off each pack's values: not specified in plan or deck; OD-60.

## Sources

- Deck slides 20, 34, 39, 40.
- Plan Phase 5 Solver task 2 and exit criteria, as recorded in [acceptance-criteria.md](../requirements/acceptance-criteria.md) §6 (AC-P5-04).
- [open-decisions.md](../open-decisions.md): OD-55, OD-56, OD-60.

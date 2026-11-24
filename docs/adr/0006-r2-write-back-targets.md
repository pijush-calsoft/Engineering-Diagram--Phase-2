# ADR-0006: First write-back targets for R2

| | |
|---|---|
| Status | **Accepted** 2026-11-24. The project owner delegated OD-4 ("you decide"); this ADR records the decision made under that delegation |
| Date | 2026-11-24 |
| Phase | Decided in Phase 0; built in Phase 7 (R2) |

## Context

Plan §11 question 4 asks which PLM or document systems are the first write-back targets in R2 (OD-4).

What the sources say:

- Phase 7 task 4: "Redlines: new DXF revision with a REDLINE layer (revision clouds, change notes, revision triangle) via ezdxf, plus a marked-up PDF; updated script and parameter table with changed rows highlighted" (plan Phase 7).
- Phase 7 task 5: "Write-back as a draft: approval workflow in the console (approve, reject, comment), then a connector writes to the target system. Connectors to PLM or document systems are built as MCP servers per engagement" (plan Phase 7).
- Principle 5: "Nothing writes back without approval" (plan §2.3). R2 exit: "no write-back possible without a recorded approval" (plan Phase 7).
- Out of scope: "native editing inside commercial CAD tools" and "any client-specific integration" (plan §1).
- Deck: "Open formats (STEP, DXF, native OpenCAD files) in Release 2. Commercial CAD needs vendor API licences; planned for Release 3" (deck slide 89). The R2 demo is "written back to STEP and DXF" (deck slide 87). The Companion's "Git writer: Branch, commit, pull request" (deck slide 47).
- OD-2 (decided 2026-11-24): the platform runs locally.

No engagement and no PLM system have been named.

## Options considered

| Option | Notes |
|---|---|
| A. Open formats inside the platform: new versioned revision in the Data Fabric plus the script in a Git repository | Needs no vendor licence or client system. Matches plan Phase 7 task 4 outputs and deck slides 47, 87, 89 |
| B. A specific PLM or document system | None is named in plan or deck. Plan Phase 7 task 5 builds these per engagement. Picking one now would be a guess |
| C. Native commercial CAD | Out of scope for the plan (§1). Deck puts it in R3 and it needs vendor API licences (deck slides 81, 90) |

## Decision

**Option A.** The first R2 write-back targets are open formats that the platform controls:

1. **Data Fabric revision.** The approved change is stored as a new dataset version (lakeFS commit, plan §4.1). It contains the redlined DXF with a REDLINE layer, the marked-up PDF, the updated STEP export, and the updated parameter table (plan Phase 7 task 4). The source drawing is never overwritten; the new version links to it through source locators (plan principle 1).
2. **Git repository for scripts.** The updated CadQuery or OpenSCAD script goes to a branch with a commit and a pull request (deck slide 47, "Git writer"). The repository is local, which fits OD-2.

Both happen only after a recorded approval in the console (plan §2.3 principle 5, Phase 7 task 5).

PLM and document-system connectors are **not** built in R2 unless an engagement names a target system. Each one is then built as an MCP server for that engagement (plan Phase 7 task 5), under that client's scope (plan principle 7).

## Consequences

- Phase 7 builds a write-back interface with two implementations (Data Fabric revision, Git branch and PR). A per-engagement MCP connector plugs in as a third without changing the approval workflow.
- No vendor licences are needed for R2 (deck slide 90 lists vendor API access as an R3 prerequisite).
- The Git server or hosting for the script repository is part of OD-18.

## Open items

- OD-18: git hosting and CI provider. Open.
- Which PLM or document system an engagement uses: decided per engagement, not here.

## Sources

- Plan §1, §2.3 (principles 1, 5, 7), §4.1, §6 Phase 7 (tasks 4, 5, exit criteria), §11 (question 4).
- Deck slides 47, 81, 87, 89, 90.
- [open-decisions.md](../open-decisions.md): OD-2, OD-4, OD-18.

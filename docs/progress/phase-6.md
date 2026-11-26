# Phase 6 log: Insight report (block 8)

| | |
|---|---|
| Plan reference | plan §6 Phase 6 (4 weeks, R1); deck slides 40, 56, 59 |
| Status | In progress. Descriptive and diagnostic report with fact check and DOCX built for the construction slice; PDF, LLM narrative, DeepEval, audit export and hardening not started |
| Last updated | 2026-11-26 |

## 1. What was built

| Item | Where |
|---|---|
| `edp-b8-report` block: Run Store from the run's artifacts plus the domain-pack files, compose, fact check, DOCX | `blocks/b8_report/` |
| Fact checker: claim references resolve to the same value; no unknown claim ids; every number in the text is a cited claim's printed form (identifiers removed first); no unfilled placeholders | `edp_b8_report.factcheck` |
| Report text from fixed templates; numbers inserted by code; diagnostic: the anchor hole nearest the peak | `edp_b8_report.compose` |
| DOCX with a "DRAFT: not signed off" line, run and pack hashes, seven sections, and a claims table with each figure's Run Store reference | `edp_b8_report.docx_writer` |
| Sign-off as a review stop (`SIGN_OFF_REQUIRED`); a failed fact check fails the run so it cannot be approved past (AC-P6-03) | `InsightReport.run` |
| Console design check (2026-11-26): editable model, margin, report with fact-check count, DOCX download, sign-off; generated model in the 3D viewer with the peak-stress point; **change the thickness and run again** as a new run, the report citing the changed value from the run's parameters next to the drawing's value | `console/src/components/Results.tsx`, `edp_orchestrator.server` (`/model`, `/report.docx`, `/rerun`), `edp_kit.overrides` |

## 2. Exit criteria (acceptance-criteria.md §7)

| ID | Status |
|---|---|
| AC-P6-01 numeric claim verification 100 % | **Met on the slice**: every claim is checked against the Run Store before release; 21 of 21 on the base-plate run |
| AC-P6-02 numbers inserted from the Run Store by code | **Met by construction**: templates hold placeholders only, and the checker rejects any number that is not a cited claim |
| AC-P6-03 a fact-check failure blocks the report | **Met**: no DOCX is written and the run fails |
| AC-P6-04 DeepEval faithfulness | Not started (no LLM narrative yet; OD-6) |
| AC-P6-05 lineage export | Not started |
| AC-P6-06 console highlight of every item | Not started for blocks 4 to 8 |
| AC-P6-07 console completion | **In progress**: margins view and a first report view built (design check tab); envelope view and report studio not started |
| AC-P6-08 hardening | Not started |

## 3. Found while building

- On the first real run the checker blocked the report: the envelope text said "(block 7)", a number with no Run Store source. The text now says "the surrogate and failure-envelope block". This is the behaviour the deck asks for (slide 40, "A mismatch blocks release").
- A placeholder with an upper-case name (`{mat.E}`) was left unfilled and was not caught, because it holds no digits. The placeholder pattern now accepts upper case, and the checker rejects any `{` or `}` left in the text.

## 4. Verification

See [phase-4.md](phase-4.md) §5 for the CI run and the end-to-end run, which cover this block.

## 4a. Demo 4 in the console (2026-11-26)

On `con-iso-base_plate-003` (580 × 290 × 15 mm, S355JR, illustrative 100 kN uplift), in the browser:

| Step | Result |
|---|---|
| Run the sample | Model, margin **0.36** (986 MPa against 355 MPa), block 6 stops for review |
| Thickness 30 mm, Run again | New run: margin **1.34** (258 MPa against 345 MPa, the 16–40 mm yield band), "Was 0.36 at 15 mm" shown; no stop at block 6 |
| Report | 22 of 22 figures traced; inputs say "thickness set to 30 mm for this run, where the drawing says 15 mm"; flags say the drawing must be revised before issue |
| Sign off | Run completed |

The 30 mm mesh is coarser (element size 15 to 3.75 mm, 9,438 elements), because element size follows the thickness; the convergence study is still open (OD-57).

## 5. Still open

PDF (WeasyPrint or Typst, plan §4.2), predictive and prescriptive levels (Release 2), the LLM narrative through the Gateway and the DeepEval judge (OD-6), report versions per audience (deck slide 59), locked signed copies (deck slide 77), the sign-off wording (OD-40, OD-61), and the report studio in the console.

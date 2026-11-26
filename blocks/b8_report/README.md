# Block 8: Insight, report

**Status: descriptive and diagnostic report built for the construction slice (2026-11-26).** Package `edp_b8_report`.

Fact-checked reports where every number is inserted from the Run Store by code (plan Phase 6; deck slide 40). Outputs: `report` (JSON, contract schema) and `docx`.

| Stage (deck slide 40) | Built |
|---|---|
| Run Store | `margins`, `solver_runs`, the design graph, the title block and the domain-pack files. A pack file whose hash differs from the solver's record stops the report (`PACK_CHANGED`) |
| Insight Builder | Descriptive: margin, stress and displacement per load case. Diagnostic: the anchor hole nearest the peak |
| Narrative Writer | Fixed templates; no language model yet |
| Report Assembler | Seven sections (summary, inputs, model, margins, envelope, flags, assumptions), and a DOCX with a claims table giving each figure's Run Store reference |
| Review and Export | A failed fact check blocks release (`FACT_CHECK_FAILED`; the run fails). Otherwise the run stops for engineer sign-off (`SIGN_OFF_REQUIRED`, OD-61) |

The fact check requires that:
- every claim's reference resolves to the same value;
- no section cites an unknown claim;
- every number in the text is the printed form of a claim that section cites, once identifiers (part numbers, load-case ids, grades) are removed;
- no placeholder is left unfilled.

Not built:
- PDF and PPTX;
- the predictive and prescriptive levels (Release 2);
- the LLM narrative and the DeepEval judge (OD-6);
- report versions per audience;
- locking signed copies.

Planned stack (plan §4.2): Jinja2 + docxtpl / python-docx, WeasyPrint or Typst, matplotlib / Plotly, DeepEval.

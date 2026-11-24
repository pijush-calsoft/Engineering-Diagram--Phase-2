# eval/suites: per-block and end-to-end evaluation

Per-block and end-to-end evaluation suites live here (plan Appendix A). The folder is empty for now: every suite needs golden data, and there is none yet (OD-7, OD-17).

## Planned suites (plan §7)

| Layer | What is measured | Tooling (plan §7) | Phase | Status |
|---|---|---|---|---|
| Parser | Dimension F1, title block accuracy, locator coverage, calibration | pytest + custom metrics on golden set | 2 | Metric functions in `edp_eval.metrics`; suite pending |
| Interpretation, KG | Feature graph match, flag resolution precision, similar-part recall | pytest, NetworkX graph diff | 3 | Pending |
| Generation | Valid solid rate, features within tolerance, Chamfer distance or volume IoU vs reference | trimesh, OCP | 4 | Pending |
| Solvers | Benchmark error, mesh convergence | Reference cases | 5 | Pending |
| Surrogate | Hold-out error, interval calibration | scikit-learn, MLflow | 5 | Pending |
| Reports | Numeric claim verification rate (must be 100 %), faithfulness, hallucination | Deterministic checker, DeepEval | 6 | Pending |
| Orchestrator | Plan correctness on scripted chat scenarios, recovery from failures | LangGraph tests, Langfuse datasets | 1 onward | Pending |
| Gateway | Model benchmarks per task, latency, cost | DeepEval, lm-evaluation-harness | 1 onward | Pending |

The Phase column is where each layer is built (plan §5, §6); the plan does not tie each suite to a phase directly.

## How suites run (plan §7)

- Every pull request runs the fast subset.
- The full golden-set suite runs nightly and gates releases.

The CI provider is not chosen yet (OD-18), so neither schedule is wired up. Which tests form the "fast subset": not specified in plan or deck; TBD in Phase 0.

## Rules for suites added later

- Read data from the Data Fabric through the manifest in `eval/golden/`. Do not copy drawings or labels into this folder. Data lives in the fabric (plan Appendix A); keeping it out of git is a repo rule (root `.gitignore`).
- Score against the targets in plan §6 (for the Parser: `edp_eval.metrics.PHASE2_TARGETS`). Targets are proposals to confirm in Phase 0 (plan §7).
- Client-scoped items are evaluated only inside that client's scope (plan Phase 0 task 2).

import { useEffect, useState } from "react";
import { api } from "../api";
import type { CadScript, Margins, Report, RunView, SolverRuns } from "../types";

// Blocks 4 to 8 in the console (deck slide 85, Demo 4): the editable model's parameters, the
// margin from the simulation, the fact-checked report and its sign-off. A person can change the
// plate thickness and run the drawing again; the first run and its report stay as they were.

export type DesignResults = {
  script: CadScript | null;
  margins: Margins | null;
  solverRuns: SolverRuns | null;
  report: Report | null;
};

type Props = {
  runId: string | null;
  view: RunView | null;
  results: DesignResults;
  previous: { runId: string; margin: number; thickness: number | null } | null;
  onRerun: (overrides: Record<string, number>) => void;
  onReview: (decision: "approve" | "reject", reviewer: string) => void;
};

const OUTLINE = ["length", "width", "thickness"];

const BLOCK_TITLE: Record<string, string> = {
  b1_parser: "Drawing parser",
  b2_interpretation: "Interpretation",
  b3_knowledge_graph: "Knowledge graph",
  b4_generation: "Generation",
  b5_opencad: "OpenCAD adapters",
  b6_solvers: "Solver connectors",
  b7_surrogate: "Surrogate",
  b8_report: "Insight report",
};

/** Three significant figures, as the report prints them. */
function sig(v: number): string {
  if (v === 0 || !Number.isFinite(v)) return String(v);
  return Number(v.toPrecision(3)).toString();
}

export function Results({ runId, view, results, previous, onRerun, onReview }: Props) {
  const { script, margins, solverRuns, report } = results;
  const thickness = script?.parameters.find((p) => p.name === "thickness");
  const [draft, setDraft] = useState("");
  const [signer, setSigner] = useState("");
  useEffect(() => setDraft(thickness ? String(thickness.value) : ""), [thickness?.value]);

  if (!runId || !view) return <p className="quiet results">Run a construction sample to see the model, margin and report.</p>;
  const byBlock = Object.fromEntries(view.status.results.map((r) => [r.block, r]));
  if (!view.domain_pack) {
    return (
      <div className="results">
        <p className="quiet">
          This run names no domain pack, so no model, simulation or report is made. Construction samples (names starting
          with <code>con-</code>) run with the construction pack.
        </p>
      </div>
    );
  }
  const noTemplate = byBlock.b4_generation?.flags.some((f) => f.code === "NO_TEMPLATE");
  const b8 = byBlock.b8_report;
  const last = view.status.results.at(-1);
  const stopped = view.status.state === "awaiting_review" && !view.running ? last : undefined;
  const awaitingSignOff = stopped?.block === "b8_report";
  const signedOff = view.status.state === "completed" && !!b8 && b8.flags.some((f) => f.code === "SIGN_OFF_REQUIRED");
  const busy = view.running;
  const proposed = Number(draft);
  const canRerun = !!thickness && !busy && Number.isFinite(proposed) && proposed > 0 && proposed !== Number(thickness.value);

  return (
    <div className="results">
      {stopped && (
        <div className="review">
          {awaitingSignOff ? (
            <p>The report is a draft until an engineer signs it off.</p>
          ) : (
            <>
              <p>
                <strong>{BLOCK_TITLE[stopped.block] ?? stopped.block}</strong> stopped for review:
              </p>
              <ul className="stop-reasons">
                {stopped.flags
                  .filter((f) => f.severity !== "info")
                  .map((f, i) => (
                    <li key={i}>{f.message}</li>
                  ))}
              </ul>
            </>
          )}
          <label htmlFor="signer">Your name or role</label>
          <input id="signer" value={signer} onChange={(e) => setSigner(e.target.value)} placeholder="e.g. structural engineer" />
          <div className="review-actions">
            <button disabled={!signer.trim()} onClick={() => onReview("approve", signer.trim())}>
              {awaitingSignOff ? "Sign off" : "Approve and continue"}
            </button>
            <button className="secondary" disabled={!signer.trim()} onClick={() => onReview("reject", signer.trim())}>
              Reject
            </button>
          </div>
        </div>
      )}
      {Object.keys(view.overrides).length > 0 && (
        <p className="override-note">
          Changed for this run:{" "}
          {Object.entries(view.overrides)
            .map(([k, v]) => `${k} ${sig(v)} mm`)
            .join(", ")}
          . The drawing is unchanged; the report says so.
        </p>
      )}

      <section aria-labelledby="h-model">
        <h2 id="h-model">Editable model</h2>
        {noTemplate && <p className="quiet">No template matches this drawing, so no model was made.</p>}
        {!script && !noTemplate && <p className="quiet">{busy ? "Generating the model…" : "No model yet."}</p>}
        {script && (
          <>
            <dl className="facts">
              {OUTLINE.map((name) => {
                const p = script.parameters.find((q) => q.name === name);
                if (!p) return null;
                const changed = !!p.comment?.includes("OVERRIDDEN");
                return (
                  <div className="fact-row" key={name}>
                    <dt>{name[0].toUpperCase() + name.slice(1)}</dt>
                    <dd>
                      {sig(Number(p.value))} mm{" "}
                      {changed ? (
                        <span className="badge badge-changed">changed</span>
                      ) : (
                        <span className="badge" title={`Dimension ${p.source.handle} on the drawing`}>
                          from drawing
                        </span>
                      )}
                    </dd>
                  </div>
                );
              })}
              <div className="fact-row">
                <dt>Holes</dt>
                <dd>{script.parameters.filter((p) => /^hole\d+_diameter$/.test(p.name)).length}</dd>
              </div>
            </dl>
            <form
              className="rerun"
              onSubmit={(e) => {
                e.preventDefault();
                if (canRerun) onRerun({ thickness: proposed });
              }}
            >
              <label htmlFor="thickness">Try another thickness (mm)</label>
              <div className="rerun-row">
                <input
                  id="thickness"
                  type="number"
                  min="1"
                  step="1"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  disabled={busy}
                />
                <button type="submit" disabled={!canRerun}>
                  Run again
                </button>
              </div>
              <p className="quiet small">
                Builds the model, simulation and report again in a new run. This run and its report are kept.
              </p>
            </form>
          </>
        )}
      </section>

      <section aria-labelledby="h-margin">
        <h2 id="h-margin">Margin</h2>
        {!margins && <p className="quiet">{busy ? "Meshing and solving (about a minute)…" : "No simulation yet."}</p>}
        {margins &&
          margins.margins.map((m, k) => {
            const run = solverRuns?.runs[k];
            const ok = m.margin >= 1;
            return (
              <div key={m.solver_run_id} className={`margin-card ${ok ? "is-ok" : "is-low"}`}>
                <div className="margin-figure">
                  <span className="margin-value">{sig(m.margin)}</span>
                  <span className="margin-label">{ok ? "margin, at or above one" : "margin, below one"}</span>
                </div>
                <dl className="facts">
                  <dt>Peak stress</dt>
                  <dd>{sig(m.computed)} MPa (von Mises)</dd>
                  <dt>Allowable</dt>
                  <dd>
                    {sig(m.allowable)} MPa
                    {run ? ` (${run.material.grade}, f_y ${sig(run.material.fy_MPa)} / γM0 ${sig(run.material.gamma_M0)})` : ""}
                  </dd>
                  {run && (
                    <>
                      <dt>Displacement</dt>
                      <dd>{sig(run.max_displacement_mm)} mm</dd>
                      <dt>Load case</dt>
                      <dd>
                        {m.load_case_id}, {sig(run.total_force_N / 1000)} kN
                        {run.illustrative_load && <span className="badge badge-changed">illustrative</span>}
                      </dd>
                    </>
                  )}
                  {solverRuns && (
                    <>
                      <dt>Mesh</dt>
                      <dd>
                        {solverRuns.mesh.elements.toLocaleString()} C3D10 elements, CalculiX
                      </dd>
                    </>
                  )}
                </dl>
                {previous && k === 0 && (
                  <p className="compare">
                    Was {sig(previous.margin)}
                    {previous.thickness !== null ? ` at ${sig(previous.thickness)} mm` : ""} in{" "}
                    <a href={`?run=${previous.runId}`}>{previous.runId}</a>.
                  </p>
                )}
              </div>
            );
          })}
      </section>

      <section aria-labelledby="h-report">
        <h2 id="h-report">Report</h2>
        {!report && (
          <p className="quiet">
            {!busy ? "No report yet." : margins ? "Writing the report…" : "Written once the simulation is done."}
          </p>
        )}
        {report && b8 && (
          <>
            <p className="fact-check">
              {b8.metrics.claims_verified} of {b8.metrics.claims} figures traced to the run's results by the fact checker.
            </p>
            <p>{report.sections.find((s) => s.key === "summary")?.text}</p>
            <details>
              <summary>All sections</summary>
              {report.sections
                .filter((s) => s.key !== "summary")
                .map((s) => (
                  <div key={s.key} className="report-section">
                    <h3>{s.key[0].toUpperCase() + s.key.slice(1)}</h3>
                    <p>{s.text}</p>
                  </div>
                ))}
            </details>
            <p>
              <a className="button-link" href={api.reportUrl(runId)} download>
                Download the report (DOCX)
              </a>
            </p>
            {awaitingSignOff && <p className="quiet small">Sign-off is at the top of this panel.</p>}
            {signedOff && <p className="signed">Signed off. The run is complete.</p>}
          </>
        )}
      </section>
    </div>
  );
}

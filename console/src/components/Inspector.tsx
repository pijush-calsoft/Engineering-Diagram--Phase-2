import { useState } from "react";
import { type Box, formatValue, zoneOf } from "../geometry";
import type { DesignGraph, DesignNode, Flag, Geometry, RunView, SimilarParts } from "../types";

const ASSOCIATION_TEXT: Record<string, string> = {
  by_value: "matched to a dimension by value",
  geometry_only: "from geometry, no dimension",
};

const FEATURE_NAME: Record<string, string> = { hole: "Hole", slot: "Slot", bend: "Bend" };

export type Selection = { key: string; handles: Set<string> } | null;

type Props = {
  geometry: Geometry | null;
  graph: DesignGraph | null;
  similar: SimilarParts | null;
  settled: { ids: Set<string>; handles: Set<string> };
  flags: Flag[];
  box: Box | null;
  view: RunView | null;
  selection: Selection;
  onSelect: (s: Selection) => void;
  onReview: (decision: "approve" | "reject", reviewer: string) => void;
};

function handlesOf(node: DesignNode): Set<string> {
  return new Set(node.sources.map((s) => s.handle).filter((h): h is string => !!h));
}

const CORROBORATION_TEXT: Record<string, string> = {
  resolved: "Confirmed by similar parts",
  conflict: "Similar parts disagree: check it",
  no_evidence: "No similar part shows this value: check it",
};

function revisionLabel(r: { part_number: string; revision: string | null }): string {
  return r.revision ? `${r.part_number} rev ${r.revision}` : r.part_number;
}

export function Inspector({ geometry, graph, similar, settled, flags, box, view, selection, onSelect, onReview }: Props) {
  const [reviewer, setReviewer] = useState("");
  const nodes = new Map(graph?.nodes.map((n) => [n.id, n]) ?? []);
  const features = graph?.nodes.filter((n) => n.kind === "feature") ?? [];
  const partDims = graph?.nodes.filter((n) => n.attributes?.association === "part_level") ?? [];
  const toggle = (key: string, handles: Set<string>) =>
    onSelect(selection?.key === key ? null : { key, handles });
  const awaiting = view?.status.state === "awaiting_review" && !view.running;

  return (
    <aside className="inspector" aria-label="What the platform read">
      {awaiting && (
        <section className="review">
          <h2>This run is waiting for your review</h2>
          <p>A block flagged something it could not settle. Check the flags below, then decide.</p>
          <label htmlFor="reviewer">Your name or role</label>
          <input id="reviewer" value={reviewer} onChange={(e) => setReviewer(e.target.value)} placeholder="e.g. design lead" />
          <div className="review-actions">
            <button disabled={!reviewer.trim()} onClick={() => onReview("approve", reviewer.trim())}>
              Approve and continue
            </button>
            <button className="secondary" disabled={!reviewer.trim()} onClick={() => onReview("reject", reviewer.trim())}>
              Reject run
            </button>
          </div>
        </section>
      )}

      {geometry?.solids && geometry.solids.length > 0 && (
        <section>
          <h2>Read from the 3D model</h2>
          {geometry.solids.map((s, i) => {
            const [x0, y0, z0, x1, y1, z1] = s.bbox;
            const unit = geometry.units ?? "units not stated";
            return (
              <dl className="facts" key={i}>
                <dt>Size</dt>
                <dd>
                  {formatValue(x1 - x0)} × {formatValue(y1 - y0)} × {formatValue(z1 - z0)} {unit}
                </dd>
                {s.volume !== null && (
                  <>
                    <dt>Volume</dt>
                    <dd>
                      {formatValue(Number(s.volume.toFixed(2)))} {geometry.units ? `${geometry.units}³` : ""}
                    </dd>
                  </>
                )}
                <dt>Faces</dt>
                <dd>{Object.entries(s.faces).map(([k, n]) => `${n} ${k}`).join(", ")}</dd>
                {s.lossy ? (
                  <>
                    <dt>Mesh</dt>
                    <dd>{s.watertight ? "closed" : "not closed"}</dd>
                    <dt>Openings</dt>
                    <dd>{s.through_holes_hint ?? "unknown"} (estimated from the mesh)</dd>
                  </>
                ) : (
                  <>
                    <dt>Holes</dt>
                    <dd>
                      {s.holes.length === 0 ? (
                        "none"
                      ) : (
                        <span className="hole-list">
                          {s.holes.map((h, j) => {
                            const key = `solid${i}.hole${j}`;
                            const handles = new Set(h.locators.map((l) => l.handle).filter((x): x is string => !!x));
                            return (
                              <button
                                key={key}
                                className={`param ${selection?.key === key ? "is-selected" : ""}`}
                                aria-pressed={selection?.key === key}
                                title={`Faces ${[...handles].join(", ")}`}
                                onClick={() => toggle(key, handles)}
                              >
                                <span className="param-name">Hole {j + 1}</span>
                                <span className="param-value">Ø{formatValue(Number(h.diameter.toFixed(4)))}</span>
                              </button>
                            );
                          })}
                        </span>
                      )}
                    </dd>
                  </>
                )}
              </dl>
            );
          })}
        </section>
      )}

      {geometry && geometry.entities.length > 0 && (
        <section>
          <h2>Read from the drawing</h2>
          <dl className="facts">
            <dt>Entities</dt>
            <dd>{geometry.entities.length}</dd>
            <dt>Dimensions</dt>
            <dd>{geometry.entities.filter((e) => e.kind === "dimension").length}</dd>
            <dt>Units</dt>
            <dd>{geometry.units ?? "not stated"}</dd>
            <dt>Layouts</dt>
            <dd>{geometry.views.join(", ") || "none"}</dd>
          </dl>
        </section>
      )}

      {graph && (
        <section>
          <h2>Features</h2>
          {features.length === 0 && <p className="quiet">No holes, slots or bends were recognised.</p>}
          <ul className="features">
            {features.map((f) => {
              const params = graph.edges.filter((e) => e.source === f.id).map((e) => nodes.get(e.target)!);
              const zone = zoneOf(f.sources[0], box);
              return (
                <li key={f.id}>
                  <button
                    className={`feature ${selection?.key === f.id ? "is-selected" : ""}`}
                    aria-pressed={selection?.key === f.id}
                    onClick={() => toggle(f.id, handlesOf(f))}
                  >
                    <span>
                      {FEATURE_NAME[f.feature_type ?? ""] ?? f.feature_type} {f.id.replace(/\D+/g, "")}
                    </span>
                    {zone && <span className="zone">zone {zone}</span>}
                  </button>
                  <ul className="params">
                    {params.map((p) => {
                      const a = p.attributes;
                      const confirmed = settled.ids.has(p.id);
                      const source = confirmed ? "from geometry, confirmed by similar parts" : ASSOCIATION_TEXT[a.association];
                      return (
                        <li key={p.id}>
                          <button
                            className={`param assoc-${confirmed ? "confirmed" : a.association} ${selection?.key === p.id ? "is-selected" : ""}`}
                            aria-pressed={selection?.key === p.id}
                            onClick={() => toggle(p.id, handlesOf(p))}
                          >
                            <span className="param-name">{a.name}</span>
                            <span className="param-value">
                              {formatValue(a.value)} {a.unit ?? ""}
                            </span>
                            {source && <span className="param-source">{source}</span>}
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </li>
              );
            })}
          </ul>
          {partDims.length > 0 && (
            <details>
              <summary>Overall dimensions ({partDims.length})</summary>
              <ul className="params">
                {partDims.map((p) => (
                  <li key={p.id}>
                    <button
                      className={`param ${selection?.key === p.id ? "is-selected" : ""}`}
                      aria-pressed={selection?.key === p.id}
                      onClick={() => toggle(p.id, handlesOf(p))}
                    >
                      <span className="param-name">{p.attributes.name}</span>
                      <span className="param-value">
                        {formatValue(p.attributes.value)} {p.attributes.unit ?? ""}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </section>
      )}

      {similar && (
        <section>
          <h2>Similar parts</h2>
          {similar.similar.length === 0 ? (
            <p className="quiet">This is the first part of its kind in the knowledge graph.</p>
          ) : (
            <ol className="similar">
              {similar.similar.map((s) => (
                <li key={s.revision_id}>
                  <span>{revisionLabel(s)}</span>
                  <span className="score">{Math.round(s.score * 100)}% alike</span>
                </li>
              ))}
            </ol>
          )}
          {similar.corroborations.map((c) => {
            const node = nodes.get(c.parameter);
            return (
              <div key={c.parameter} className={`corroboration status-${c.status}`}>
                <button
                  className={`param ${selection?.key === c.parameter ? "is-selected" : ""}`}
                  aria-pressed={selection?.key === c.parameter}
                  onClick={() => node && toggle(c.parameter, handlesOf(node))}
                >
                  <span className="param-name">{c.parameter}</span>
                  <span className="param-value">
                    {formatValue(c.value)} {node?.attributes.unit ?? ""}
                  </span>
                  <span className="param-source">
                    {CORROBORATION_TEXT[c.status]}, confidence {c.confidence.toFixed(2)}
                  </span>
                </button>
                <ul className="evidence">
                  {c.evidence.map((e, i) => (
                    <li key={i} className={e.agrees ? "agrees" : "disagrees"}>
                      {revisionLabel(e)}: {formatValue(e.value)} {e.agrees ? "agrees" : "differs"}
                      {e.same_part ? "" : " (other part, supporting only)"}
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </section>
      )}

      {view && (
        <section>
          <h2>Flags</h2>
          {flags.length === 0 ? (
            <p className="quiet">No flags. Every value has a source on the drawing.</p>
          ) : (
            <ul className="flags">
              {flags.map((f, i) => {
                const handle = f.target?.handle;
                const key = `flag-${i}`;
                const isSettled = f.code === "LOW_CONFIDENCE" && !!handle && settled.handles.has(handle);
                return (
                  <li key={key}>
                    <button
                      className={`flag severity-${isSettled ? "info" : f.severity} ${selection?.key === key ? "is-selected" : ""}`}
                      disabled={!handle}
                      onClick={() => handle && toggle(key, new Set([handle]))}
                    >
                      <span className="flag-code">{f.code.replaceAll("_", " ").toLowerCase()}</span>
                      <span className="flag-message">
                        {f.message}
                        {isSettled && " Settled: confirmed by the knowledge graph."}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      )}
    </aside>
  );
}

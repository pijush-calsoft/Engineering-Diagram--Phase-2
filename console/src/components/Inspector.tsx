import { useState } from "react";
import { type Box, formatValue, zoneOf } from "../geometry";
import type { DesignGraph, DesignNode, Flag, Geometry, RunView } from "../types";

const ASSOCIATION_TEXT: Record<string, string> = {
  by_value: "matched to a dimension by value",
  geometry_only: "from geometry, no dimension",
};

const FEATURE_NAME: Record<string, string> = { hole: "Hole", slot: "Slot", bend: "Bend" };

export type Selection = { key: string; handles: Set<string> } | null;

type Props = {
  geometry: Geometry | null;
  graph: DesignGraph | null;
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

export function Inspector({ geometry, graph, flags, box, view, selection, onSelect, onReview }: Props) {
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

      {geometry && (
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
                      return (
                        <li key={p.id}>
                          <button
                            className={`param assoc-${a.association} ${selection?.key === p.id ? "is-selected" : ""}`}
                            aria-pressed={selection?.key === p.id}
                            onClick={() => toggle(p.id, handlesOf(p))}
                          >
                            <span className="param-name">{a.name}</span>
                            <span className="param-value">
                              {formatValue(a.value)} {a.unit ?? ""}
                            </span>
                            {ASSOCIATION_TEXT[a.association] && (
                              <span className="param-source">{ASSOCIATION_TEXT[a.association]}</span>
                            )}
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
                return (
                  <li key={key}>
                    <button
                      className={`flag severity-${f.severity} ${selection?.key === key ? "is-selected" : ""}`}
                      disabled={!handle}
                      onClick={() => handle && toggle(key, new Set([handle]))}
                    >
                      <span className="flag-code">{f.code.replaceAll("_", " ").toLowerCase()}</span>
                      <span className="flag-message">{f.message}</span>
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

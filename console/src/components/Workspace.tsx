import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { type Box, formatValue, ZONE_COLS, ZONE_ROWS } from "../geometry";
import type { DesignGraph, DesignNode, Entity, Geometry } from "../types";

// Drawing workspace (plan Phase 6 "drawing workspace with per-agent layers"; Phase 2 task 6).
// The parser's geometry redrawn as SVG, with pan and zoom, layer switches, the features block 2
// recognised as markers, and, for scans, the scanned image underneath what was read.

export type Layer = "geometry" | "dimensions" | "notes" | "features" | "flags" | "scan";
const LAYER_TEXT: Record<Layer, string> = {
  geometry: "Geometry",
  dimensions: "Dimensions",
  notes: "Notes",
  features: "Features",
  flags: "Flags",
  scan: "Scan image",
};
const FEATURE_LETTER: Record<string, string> = { hole: "H", slot: "S", bend: "B", pocket: "P", boss: "X", rib: "R" };
const DIM_PREFIX: Record<string, string> = { diameter: "Ø", radius: "R" };
const LETTERS = "ABCDEFGH";
const ZOOM_STEP = 1.25;
// Dimension labels are at least this share of the visible width (about 11 px on a 1200 px canvas).
const MIN_LABEL_FRACTION = 0.009;

type View = { x: number; y: number; w: number; h: number };
export type Scan = { url: string; w: number; h: number };

type Props = {
  geometry: Geometry | null;
  graph: DesignGraph | null;
  box: Box | null;
  scan: Scan | null;
  traced: Set<string>;
  flagged: Set<string>;
  selectedKey: string | null;
  onSelect: (key: string, handles: Set<string>) => void;
  titleBlock: ReactNode;
  empty: ReactNode;
};

function arcPath(cx: number, cy: number, r: number, a0: number, a1: number): string {
  const sweep = (((a1 - a0) % 360) + 360) % 360 || 360;
  const p = (a: number) => [cx + r * Math.cos((a * Math.PI) / 180), -(cy + r * Math.sin((a * Math.PI) / 180))];
  const [x0, y0] = p(a0);
  const [x1, y1] = p(a0 + sweep);
  // y is negated for the screen, so the CAD counter-clockwise sweep is drawn with sweep-flag 0.
  return `M ${x0} ${y0} A ${r} ${r} 0 ${sweep > 180 ? 1 : 0} 0 ${x1} ${y1}`;
}

function layerOf(e: Entity): Layer {
  return e.kind === "dimension" ? "dimensions" : e.kind === "text" ? "notes" : "geometry";
}

function describe(e: Entity): string {
  const d = e.data;
  if (e.kind === "dimension") return `Dimension ${DIM_PREFIX[d.dimtype] ?? ""}${formatValue(d.value)} (${d.dimtype})`;
  if (e.kind === "text") return `Text "${d.text}"`;
  if (e.kind === "circle") return `Circle, diameter ${formatValue(2 * d.radius)}`;
  if (e.kind === "arc") return `Arc, radius ${formatValue(d.radius)}`;
  return e.kind[0].toUpperCase() + e.kind.slice(1);
}

function EntityShape({ e, textHeight, minLabel }: { e: Entity; textHeight: number; minLabel: number }) {
  const d = e.data;
  switch (e.kind) {
    case "line":
      return <line x1={d.start[0]} y1={-d.start[1]} x2={d.end[0]} y2={-d.end[1]} />;
    case "circle":
      return <circle cx={d.center[0]} cy={-d.center[1]} r={d.radius} />;
    case "arc":
      return <path d={arcPath(d.center[0], d.center[1], d.radius, d.start_angle, d.end_angle)} />;
    case "spline":
      return <polyline points={(d.control_points as number[][]).map(([x, y]) => `${x},${-y}`).join(" ")} />;
    case "text": {
      const b = e.locator.bbox;
      if (!b) return null;
      return (
        <text x={b[0]} y={-b[1]} fontSize={(b[3] - b[1]) * 0.95} className="sheet-text">
          {d.text}
        </text>
      );
    }
    case "dimension": {
      const b = e.locator.bbox;
      const at: number[] | undefined = d.text_at ?? (b ? [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2] : undefined);
      if (!at) return null;
      const label = `${DIM_PREFIX[d.dimtype] ?? ""}${formatValue(d.value)}`;
      const points: number[][] = d.p1 && d.p2 ? [d.p1, d.p2] : d.center ? [d.center] : [];
      return (
        <g className="dimension">
          {points.length === 2 && (
            <line x1={points[0][0]} y1={-points[0][1]} x2={points[1][0]} y2={-points[1][1]} className="dim-measure" />
          )}
          {points.map(([x, y], i) => (
            <circle key={i} cx={x} cy={-y} r={textHeight * 0.35} className="dim-point" />
          ))}
          {/* Scans: the box the model read the value from. */}
          {d.from_text && b && (
            <rect x={b[0]} y={-b[3]} width={b[2] - b[0]} height={b[3] - b[1]} className="read-box" />
          )}
          {/* True size when zoomed in; never smaller than a readable size on screen. */}
          <text x={at[0]} y={-at[1]} fontSize={Math.max(d.text_height || textHeight, minLabel)} className="dim-text">
            {label}
          </text>
        </g>
      );
    }
  }
}

/** Median height of the drawing's own text, for dimension labels placed without a height. */
function typicalTextHeight(entities: Entity[], fallback: number): number {
  const hs = entities
    .filter((e) => e.kind === "text" && e.locator.bbox)
    .map((e) => e.locator.bbox![3] - e.locator.bbox![1])
    .sort((a, b) => a - b);
  return hs.length ? hs[Math.floor(hs.length / 2)] : fallback;
}

function unionBox(bs: (number[] | null)[]): [number, number, number, number] | null {
  let out: [number, number, number, number] | null = null;
  for (const b of bs) {
    if (!b) continue;
    out = out ? [Math.min(out[0], b[0]), Math.min(out[1], b[1]), Math.max(out[2], b[2]), Math.max(out[3], b[3])] : [b[0], b[1], b[2], b[3]];
  }
  return out;
}

export function Workspace({ geometry, graph, box, scan, traced, flagged, selectedKey, onSelect, titleBlock, empty }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const drag = useRef<{ x: number; y: number; view: View } | null>(null);
  const [layers, setLayers] = useState<Record<Layer, boolean>>({
    geometry: true,
    dimensions: true,
    notes: true,
    features: true,
    flags: true,
    scan: true,
  });
  const [hover, setHover] = useState<string | null>(null);
  const [showTitle, setShowTitle] = useState(true);

  const frame = useMemo(() => {
    if (!box) return null;
    const w = box.x1 - box.x0;
    const h = box.y1 - box.y0;
    const band = Math.max(w, h) * 0.035;
    return { w, h, band, full: { x: box.x0 - band, y: -box.y1 - band, w: w + 2 * band, h: h + 2 * band } };
  }, [box]);
  const [view, setView] = useState<View | null>(null);
  useEffect(() => setView(frame?.full ?? null), [frame]);

  const byHandle = useMemo(() => {
    const m = new Map<string, Entity>();
    for (const e of geometry?.entities ?? []) if (e.locator.handle) m.set(e.locator.handle, e);
    return m;
  }, [geometry]);

  const features = useMemo(() => {
    const out: { node: DesignNode; label: string; bbox: [number, number, number, number]; handles: Set<string> }[] = [];
    const counts: Record<string, number> = {};
    for (const n of graph?.nodes ?? []) {
      if (n.kind !== "feature") continue;
      const handles = new Set(n.sources.map((s) => s.handle).filter((h): h is string => !!h));
      const bbox = unionBox([...handles].map((h) => byHandle.get(h)?.locator.bbox ?? null));
      if (!bbox) continue;
      const letter = FEATURE_LETTER[n.feature_type ?? ""] ?? "F";
      counts[letter] = (counts[letter] ?? 0) + 1;
      out.push({ node: n, label: `${letter}${counts[letter]}`, bbox, handles });
    }
    return out;
  }, [graph, byHandle]);

  const counts = useMemo(() => {
    const c: Record<Layer, number> = { geometry: 0, dimensions: 0, notes: 0, features: features.length, flags: flagged.size, scan: scan ? 1 : 0 };
    for (const e of geometry?.entities ?? []) c[layerOf(e)] += 1;
    return c;
  }, [geometry, features, flagged, scan]);

  const toSvg = useCallback((clientX: number, clientY: number) => {
    const svg = svgRef.current;
    const ctm = svg?.getScreenCTM();
    if (!svg || !ctm) return null;
    const p = svg.createSVGPoint();
    p.x = clientX;
    p.y = clientY;
    return p.matrixTransform(ctm.inverse());
  }, []);

  const zoomAt = useCallback(
    (factor: number, cx?: number, cy?: number) => {
      setView((v) => {
        if (!v || !frame) return v;
        const w = Math.min(Math.max(v.w / factor, frame.full.w / 60), frame.full.w * 4);
        const k = w / v.w;
        const px = cx ?? v.x + v.w / 2;
        const py = cy ?? v.y + v.h / 2;
        return { x: px - (px - v.x) * k, y: py - (py - v.y) * k, w, h: v.h * k };
      });
    },
    [frame],
  );

  // Wheel zoom around the pointer; registered natively so the page does not scroll.
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const onWheel = (ev: WheelEvent) => {
      ev.preventDefault();
      const p = toSvg(ev.clientX, ev.clientY);
      zoomAt(ev.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP, p?.x, p?.y);
    };
    svg.addEventListener("wheel", onWheel, { passive: false });
    return () => svg.removeEventListener("wheel", onWheel);
  }, [toSvg, zoomAt, frame]);

  if (!geometry || !box || !frame || !view) {
    return <div className="workspace-empty">{empty}</div>;
  }
  const { w, h, band } = frame;
  const label = band * 0.55;
  const textHeight = typicalTextHeight(geometry.entities, Math.max(w, h) * 0.012);
  const zoom = frame.full.w / view.w;
  const minLabel = view.w * MIN_LABEL_FRACTION;

  const onPointerDown = (ev: React.PointerEvent<SVGSVGElement>) => {
    if ((ev.target as Element).closest(".feature-mark")) return;
    ev.currentTarget.setPointerCapture(ev.pointerId);
    drag.current = { x: ev.clientX, y: ev.clientY, view };
  };
  const onPointerMove = (ev: React.PointerEvent<SVGSVGElement>) => {
    const d = drag.current;
    const ctm = svgRef.current?.getScreenCTM();
    if (!d || !ctm) return;
    setView({ ...d.view, x: d.view.x - (ev.clientX - d.x) / ctm.a, y: d.view.y - (ev.clientY - d.y) / ctm.d });
  };
  const endDrag = () => {
    drag.current = null;
  };
  const onKey = (ev: React.KeyboardEvent) => {
    if (ev.key === "+" || ev.key === "=") zoomAt(ZOOM_STEP);
    else if (ev.key === "-") zoomAt(1 / ZOOM_STEP);
    else if (ev.key === "0") setView(frame.full);
    else return;
    ev.preventDefault();
  };

  return (
    <div className="workspace-pane">
      <div className="ws-toolbar" role="toolbar" aria-label="Drawing view">
        <div className="ws-zoom">
          <button className="tool" onClick={() => zoomAt(1 / ZOOM_STEP)} aria-label="Zoom out">
            −
          </button>
          <span className="zoom-level" aria-live="polite">
            {Math.round(zoom * 100)}%
          </span>
          <button className="tool" onClick={() => zoomAt(ZOOM_STEP)} aria-label="Zoom in">
            +
          </button>
          <button className="tool" onClick={() => setView(frame.full)}>
            Fit
          </button>
        </div>
        <div className="ws-layers" aria-label="Layers">
          {(Object.keys(LAYER_TEXT) as Layer[])
            .filter((l) => l !== "scan" || scan)
            .map((l) => (
              <button
                key={l}
                className={`layer layer-${l}`}
                aria-pressed={layers[l]}
                onClick={() => setLayers((s) => ({ ...s, [l]: !s[l] }))}
              >
                {LAYER_TEXT[l]}
                <span className="layer-count">{counts[l]}</span>
              </button>
            ))}
          <button className="layer" aria-pressed={showTitle} onClick={() => setShowTitle((s) => !s)}>
            Title block
          </button>
        </div>
      </div>
      <div className="ws-canvas">
        <svg
          ref={svgRef}
          viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`}
          preserveAspectRatio="xMidYMid meet"
          role="img"
          tabIndex={0}
          aria-label="Drawing as read by the parser. Drag to pan, scroll or press plus and minus to zoom, 0 to fit."
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
          onKeyDown={onKey}
        >
          <rect x={box.x0 - band} y={-box.y1 - band} width={w + 2 * band} height={h + 2 * band} className="paper" />
          {scan && layers.scan && <image href={scan.url} x={0} y={-scan.h} width={scan.w} height={scan.h} className="scan-image" />}
          <g className="zone-band" aria-hidden="true">
            <rect x={box.x0 - band} y={-box.y1 - band} width={w + 2 * band} height={h + 2 * band} className="frame-outer" />
            <rect x={box.x0} y={-box.y1} width={w} height={h} className="frame-inner" />
            {Array.from({ length: ZONE_COLS }, (_, i) => (
              <text key={`n${i}`} x={box.x0 + ((i + 0.5) * w) / ZONE_COLS} y={-box.y1 - band / 2} fontSize={label}>
                {i + 1}
              </text>
            ))}
            {Array.from({ length: ZONE_ROWS }, (_, i) => (
              <text key={`l${i}`} x={box.x0 - band / 2} y={-box.y1 + ((i + 0.5) * h) / ZONE_ROWS} fontSize={label}>
                {LETTERS[i]}
              </text>
            ))}
          </g>
          <g className="zone-grid" aria-hidden="true">
            {Array.from({ length: ZONE_COLS - 1 }, (_, i) => {
              const x = box.x0 + ((i + 1) * w) / ZONE_COLS;
              return <line key={`c${i}`} x1={x} y1={-box.y1} x2={x} y2={-box.y0} />;
            })}
            {Array.from({ length: ZONE_ROWS - 1 }, (_, i) => {
              const y = -box.y1 + ((i + 1) * h) / ZONE_ROWS;
              return <line key={`r${i}`} x1={box.x0} y1={y} x2={box.x1} y2={y} />;
            })}
          </g>
          {geometry.entities.map((e, i) => {
            if (!layers[layerOf(e)]) return null;
            const handle = e.locator.handle ?? "";
            const cls = [`ent ent-${e.kind}`, traced.has(handle) && "traced", layers.flags && flagged.has(handle) && "flagged"]
              .filter(Boolean)
              .join(" ");
            return (
              <g key={i} className={cls} onPointerEnter={() => setHover(`${describe(e)}, handle ${handle || "none"}`)} onPointerLeave={() => setHover(null)}>
                <EntityShape e={e} textHeight={textHeight} minLabel={minLabel} />
              </g>
            );
          })}
          {layers.features &&
            features.map((f) => {
              const pad = textHeight * 0.6;
              const [x0, y0, x1, y1] = f.bbox;
              const on = selectedKey === f.node.id;
              return (
                <g
                  key={f.node.id}
                  className={`feature-mark ${on ? "on" : ""}`}
                  role="button"
                  aria-label={`${f.node.feature_type} ${f.label}`}
                  onClick={() => onSelect(f.node.id, f.handles)}
                  onPointerEnter={() => setHover(`${f.node.feature_type} ${f.label} (${f.node.id}): click to trace`)}
                  onPointerLeave={() => setHover(null)}
                >
                  <rect x={x0 - pad} y={-y1 - pad} width={x1 - x0 + 2 * pad} height={y1 - y0 + 2 * pad} rx={pad} />
                  <text x={x0 - pad} y={-y1 - pad * 1.4} fontSize={textHeight * 1.1}>
                    {f.label}
                  </text>
                </g>
              );
            })}
        </svg>
        {showTitle && <div className="ws-title">{titleBlock}</div>}
        <p className="ws-readout" aria-live="polite">
          {hover ?? "Drag to pan, scroll to zoom. Select a value on the right, or a feature marker, to trace it."}
        </p>
      </div>
    </div>
  );
}

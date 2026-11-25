import type { ReactNode } from "react";
import { type Box, formatValue, ZONE_COLS, ZONE_ROWS } from "../geometry";
import type { Entity, Geometry } from "../types";

type Props = {
  geometry: Geometry | null;
  box: Box | null;
  traced: Set<string>;
  flagged: Set<string>;
  titleBlock: ReactNode;
  empty: ReactNode;
};

const LETTERS = "ABCDEFGH";
const DIM_PREFIX: Record<string, string> = { diameter: "Ø", radius: "R" };

function arcPath(cx: number, cy: number, r: number, a0: number, a1: number): string {
  const sweep = (((a1 - a0) % 360) + 360) % 360 || 360;
  const p = (a: number) => [cx + r * Math.cos((a * Math.PI) / 180), -(cy + r * Math.sin((a * Math.PI) / 180))];
  const [x0, y0] = p(a0);
  const [x1, y1] = p(a0 + sweep);
  // y is negated for the screen, so the CAD counter-clockwise sweep is drawn with sweep-flag 0.
  return `M ${x0} ${y0} A ${r} ${r} 0 ${sweep > 180 ? 1 : 0} 0 ${x1} ${y1}`;
}

function EntityShape({ e, textHeight }: { e: Entity; textHeight: number }) {
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
          {/* Measured points: shown when the dimension is traced. */}
          {points.length === 2 && (
            <line x1={points[0][0]} y1={-points[0][1]} x2={points[1][0]} y2={-points[1][1]} className="dim-measure" />
          )}
          {points.map(([x, y], i) => (
            <circle key={i} cx={x} cy={-y} r={textHeight * 0.35} className="dim-point" />
          ))}
          <text x={at[0]} y={-at[1]} fontSize={Math.max(d.text_height ?? 0, textHeight)} className="dim-text">
            {label}
          </text>
        </g>
      );
    }
  }
}

/** Median height of the drawing's own text, used for labels the parser placed without a height. */
function typicalTextHeight(entities: Entity[]): number | null {
  const hs = entities
    .filter((e) => e.kind === "text" && e.locator.bbox)
    .map((e) => e.locator.bbox![3] - e.locator.bbox![1])
    .sort((a, b) => a - b);
  return hs.length ? hs[Math.floor(hs.length / 2)] : null;
}

export function DrawingSheet({ geometry, box, traced, flagged, titleBlock, empty }: Props) {
  if (!geometry || !box) {
    return <div className="sheet sheet-empty">{empty}</div>;
  }
  const w = box.x1 - box.x0;
  const h = box.y1 - box.y0;
  // Zone border band around the drawing, labelled like a paper sheet (numbers across, letters down).
  const band = Math.max(w, h) * 0.035;
  const label = band * 0.55;
  // Dimension values at true scale are often too small on screen; never draw them below this size.
  // Plain drawing text keeps its own size, because its line spacing is fixed in the drawing.
  const minText = Math.max(w, h) * 0.016;
  const textHeight = Math.max(typicalTextHeight(geometry.entities) ?? 0, minText);
  return (
    <div className="sheet">
      <div className="sheet-field">
        <svg
          viewBox={`${box.x0 - band} ${-box.y1 - band} ${w + 2 * band} ${h + 2 * band}`}
          preserveAspectRatio="xMidYMin meet"
          role="img"
          aria-label="Drawing as read by the parser"
        >
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
            const handle = e.locator.handle ?? "";
            const cls = [`ent ent-${e.kind}`, traced.has(handle) && "traced", flagged.has(handle) && "flagged"]
              .filter(Boolean)
              .join(" ");
            return (
              <g key={i} className={cls}>
                <EntityShape e={e} textHeight={textHeight} />
              </g>
            );
          })}
        </svg>
        {titleBlock}
      </div>
    </div>
  );
}

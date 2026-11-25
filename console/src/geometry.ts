import type { Entity, Locator } from "./types";

export type Box = { x0: number; y0: number; x1: number; y1: number };

export function bounds(entities: Entity[]): Box | null {
  let box: Box | null = null;
  for (const e of entities) {
    const b = e.locator.bbox;
    if (!b) continue;
    box = box
      ? { x0: Math.min(box.x0, b[0]), y0: Math.min(box.y0, b[1]), x1: Math.max(box.x1, b[2]), y1: Math.max(box.y1, b[3]) }
      : { x0: b[0], y0: b[1], x1: b[2], y1: b[3] };
  }
  return box;
}

// Drawing-sheet zones, as on paper drawings: numbers along the width, letters up the height
// (letters run from the top edge down).
export const ZONE_COLS = 8;
export const ZONE_ROWS = 6;
const LETTERS = "ABCDEFGH";

export function zoneOf(loc: Locator | undefined, box: Box | null): string | null {
  if (!loc?.bbox || !box) return null;
  const cx = (loc.bbox[0] + loc.bbox[2]) / 2;
  const cy = (loc.bbox[1] + loc.bbox[3]) / 2;
  const col = Math.min(ZONE_COLS - 1, Math.max(0, Math.floor(((cx - box.x0) / (box.x1 - box.x0 || 1)) * ZONE_COLS)));
  const row = Math.min(ZONE_ROWS - 1, Math.max(0, Math.floor(((box.y1 - cy) / (box.y1 - box.y0 || 1)) * ZONE_ROWS)));
  return `${LETTERS[row]}${col + 1}`;
}

export function formatValue(value: number): string {
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(4)));
}

/** The drawing extents plus a margin; the sheet and its zones cover this box. */
export function sheetBox(entities: Entity[]): Box | null {
  const b = bounds(entities);
  if (!b) return null;
  const pad = Math.max(b.x1 - b.x0, b.y1 - b.y0) * 0.06;
  return { x0: b.x0 - pad, y0: b.y0 - pad, x1: b.x1 + pad, y1: b.y1 + pad };
}

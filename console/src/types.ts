// Mirrors edp_contracts (geometry, design_graph) and edp_orchestrator.server responses.

export type Locator = {
  file_id: string;
  version: string;
  view: string | null;
  layer: string | null;
  handle: string | null;
  bbox: [number, number, number, number] | null;
  confidence: number;
};

export type Entity = {
  kind: "line" | "arc" | "circle" | "spline" | "text" | "dimension";
  locator: Locator;
  data: Record<string, any>;
};

export type TitleField = { value: string | null; locator: Locator } | null;

export type Hole3D = {
  diameter: number;
  axis_origin: [number, number, number];
  axis_direction: [number, number, number];
  locators: Locator[];
};

export type Solid = {
  locator: Locator;
  bbox: [number, number, number, number, number, number];
  volume: number | null;
  faces: Record<string, number>;
  edges: number | null;
  holes: Hole3D[];
  watertight: boolean | null;
  through_holes_hint: number | null;
  lossy: boolean;
};

export type Geometry = {
  views: string[];
  units: string | null;
  scale: string | null;
  entities: Entity[];
  title_block: Record<string, TitleField> | null;
  solids?: Solid[];
};

export type DesignNode = {
  id: string;
  kind: "feature" | "parameter" | "tolerance" | "datum" | "material" | "requirement";
  feature_type: string | null;
  attributes: Record<string, any>;
  sources: Locator[];
};

export type DesignGraph = {
  nodes: DesignNode[];
  edges: { source: string; target: string; relation: string }[];
};

export type Flag = {
  code: string;
  message: string;
  target: Locator | null;
  severity: "info" | "review" | "block";
};

export type BlockResultRecord = { block: string; status: string; metrics: Record<string, any>; flags: Flag[] };

export type RunView = {
  status: {
    run_id: string;
    state: "completed" | "awaiting_review" | "stopped" | "rejected" | "unknown";
    next: string[];
    results: BlockResultRecord[];
    error: string | null;
  };
  running: boolean;
  upload: { file_id: string; dataset_id: string; commit: string; kind: string; filename: string } | null;
  artifacts: { id: string; block: string; kind: string; uri: string }[];
};

export type BlockInfo = { name: string; version: string; real: boolean };

export type RunEvent = { seq: number; subject: string; payload: Record<string, any> };

export type BlockState = "waiting" | "running" | "done" | "review" | "failed";

export type Evidence = {
  part_number: string;
  revision: string | null;
  value: number;
  value_mm: number;
  agrees: boolean;
  same_part: boolean;
};

export type SimilarParts = {
  part: { revision_id: string; part_number: string; revision: string | null };
  similar: { revision_id: string; part_number: string; revision: string | null; score: number }[];
  corroborations: {
    parameter: string;
    name: string;
    value: number;
    status: "resolved" | "conflict" | "no_evidence";
    confidence: number;
    evidence: Evidence[];
  }[];
};

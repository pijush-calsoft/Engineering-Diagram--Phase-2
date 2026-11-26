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
  domain_pack: string | null;
  parent: string | null;
  overrides: Record<string, number>;
};

// Blocks 4 to 8 (cad_script, margins, solver_runs, report in edp_contracts.artifacts).
export type ScriptParameter = { name: string; value: number | string; unit: string | null; comment: string | null; source: Locator };

export type CadScript = { language: string; code: string; parameters: ScriptParameter[] };

export type Margin = {
  load_case_id: string;
  allowable: number;
  computed: number;
  margin: number;
  solver_run_id: string;
  governing_location: Locator;
};

export type Margins = { margins: Margin[] };

export type SolverRun = {
  solver_run_id: string;
  solver: string;
  load_case_id: string;
  illustrative_load: boolean;
  material: { grade: string; fy_MPa: number; gamma_M0: number; E_MPa: number };
  total_force_N: number;
  max_von_mises_MPa: number;
  max_point_mm: [number, number, number];
  max_displacement_mm: number;
  allowable_MPa: number;
  seconds: number;
};

export type SolverRuns = {
  domain_pack: string;
  mesh: { elements: number; nodes: number; size_max_mm: number; size_min_mm: number; min_scaled_jacobian: number | null };
  runs: SolverRun[];
};

export type ReportSection = { key: string; text: string; claim_ids: string[] };

export type Report = {
  run_id: string;
  sections: ReportSection[];
  claims: { id: string; value: number; unit: string | null; run_store_ref: string }[];
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

export type ChatStatus = { available: boolean; reason: string | null; model: string | null };

export type Citation = { id: string; text: string; handles: string[] };

export type CitedAnswer = {
  answer: string;
  from_facts: boolean;
  citations: Citation[];
  flags: Flag[];
  cost_usd: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  facts: number;
};

export type Spend = { spent_usd: number; calls: number };

export type RunSummary = {
  run_id: string;
  filename: string;
  kind: string;
  data_class: string;
  state: string;
  running: boolean;
  started: number;
  parent: string | null;
  overrides: Record<string, number>;
};

export type Mesh = {
  positions: number[];
  indices: number[];
  faces: { handle: string | null; start: number; count: number }[];
  bbox: [number, number, number, number, number, number];
};

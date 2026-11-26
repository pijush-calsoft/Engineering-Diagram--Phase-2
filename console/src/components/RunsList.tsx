import type { RunSummary } from "../types";

// Files and runs of this console session (plan Phase 6 console: "files"), newest first.

const KIND_TEXT: Record<string, string> = {
  dxf: "DXF",
  dwg: "DWG",
  pdf: "PDF",
  image: "Scan",
  step: "STEP",
  iges: "IGES",
  stl: "STL",
};

const STATE_TEXT: Record<string, string> = {
  completed: "Completed",
  awaiting_review: "Waiting for review",
  stopped: "Stopped",
  rejected: "Rejected",
  unknown: "Starting",
};

function age(started: number): string {
  const s = Math.max(0, Date.now() / 1000 - started);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  return `${Math.floor(s / 3600)} h ago`;
}

type Props = { runs: RunSummary[]; current: string | null; onOpen: (id: string) => void };

export function RunsList({ runs, current, onOpen }: Props) {
  return (
    <aside className="runs" aria-label="Runs in this session">
      <h2>Runs</h2>
      {runs.length === 0 ? (
        <p className="quiet">Runs you start appear here.</p>
      ) : (
        <ol>
          {runs.map((r) => (
            <li key={r.run_id}>
              <button
                className={`run-item state-${r.running ? "running" : r.state}`}
                aria-current={r.run_id === current ? "true" : undefined}
                onClick={() => onOpen(r.run_id)}
              >
                <span className="run-file">{r.filename}</span>
                <span className="run-meta">
                  <span className="run-kind">{KIND_TEXT[r.kind] ?? r.kind}</span>
                  <span>{r.running ? "Running" : STATE_TEXT[r.state] ?? r.state}</span>
                  <span>{age(r.started)}</span>
                </span>
                {r.data_class === "client" && <span className="run-client">client data</span>}
              </button>
            </li>
          ))}
        </ol>
      )}
    </aside>
  );
}

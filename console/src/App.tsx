import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, watchRun } from "./api";
import { DrawingSheet } from "./components/DrawingSheet";
import { Inspector, type Selection } from "./components/Inspector";
import { Pipeline } from "./components/Pipeline";
import { sheetBox } from "./geometry";
import type { BlockInfo, BlockState, DesignGraph, Flag, Geometry, RunEvent, RunView, SimilarParts } from "./types";

const RUN_STATE_TEXT: Record<string, string> = {
  completed: "Completed",
  awaiting_review: "Waiting for review",
  stopped: "Stopped on an error",
  rejected: "Rejected",
  unknown: "Starting",
};

function stateFromEvent(e: RunEvent): BlockState | null {
  if (e.subject === "run.block.started") return "running";
  if (e.subject === "run.block.failed") return "failed";
  if (e.subject === "run.block.completed") return e.payload.status === "needs_review" ? "review" : "done";
  return null;
}

export function App() {
  const [blocks, setBlocks] = useState<BlockInfo[]>([]);
  const [samples, setSamples] = useState<string[]>([]);
  const [sample, setSample] = useState("");
  const [runId, setRunId] = useState<string | null>(null);
  const [view, setView] = useState<RunView | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [states, setStates] = useState<Record<string, BlockState>>({});
  const [geometry, setGeometry] = useState<Geometry | null>(null);
  const [graph, setGraph] = useState<DesignGraph | null>(null);
  const [similar, setSimilar] = useState<SimilarParts | null>(null);
  const [selection, setSelection] = useState<Selection>(null);
  const [error, setError] = useState<string | null>(null);
  const loaded = useRef<Set<string>>(new Set());
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.blocks().then(setBlocks).catch((e) => setError(`Cannot reach the console API: ${e.message}`));
    api.samples().then((s) => {
      setSamples(s);
      setSample(s[0] ?? "");
    });
  }, []);

  const refresh = useCallback(async (id: string) => {
    const v = await api.run(id);
    setView(v);
    for (const a of v.artifacts) {
      if (loaded.current.has(a.uri)) continue;
      if (a.kind === "geometry") {
        loaded.current.add(a.uri);
        setGeometry(await api.artifact<Geometry>(a.uri));
      } else if (a.kind === "design_graph") {
        loaded.current.add(a.uri);
        setGraph(await api.artifact<DesignGraph>(a.uri));
      } else if (a.kind === "similar_parts" && a.uri.startsWith("fabric://")) {
        loaded.current.add(a.uri);
        setSimilar(await api.artifact<SimilarParts>(a.uri));
      }
    }
  }, []);

  const follow = useCallback(
    (id: string) =>
      watchRun(
        id,
        (e) => {
          setEvents((prev) => (prev.some((p) => p.seq === e.seq) ? prev : [...prev, e]));
          const s = stateFromEvent(e);
          if (s) setStates((prev) => ({ ...prev, [e.payload.block]: s }));
          if (e.subject === "run.block.completed") refresh(id);
        },
        () => refresh(id),
      ),
    [refresh],
  );

  // A run can be opened by link: ?run=<id>
  useEffect(() => {
    const id = new URLSearchParams(location.search).get("run");
    if (!id) return;
    setRunId(id);
    refresh(id).then(() => follow(id)).catch((e) => setError(`Cannot open run ${id}: ${e.message}`));
  }, [refresh, follow]);

  const begin = async (start: () => Promise<{ run_id: string }>) => {
    setError(null);
    setView(null);
    setEvents([]);
    setStates({});
    setGeometry(null);
    setGraph(null);
    setSimilar(null);
    setSelection(null);
    loaded.current = new Set();
    try {
      const { run_id } = await start();
      setRunId(run_id);
      history.replaceState(null, "", `?run=${run_id}`);
      follow(run_id);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const review = async (decision: "approve" | "reject", reviewer: string) => {
    if (!runId) return;
    try {
      await api.review(runId, decision, reviewer);
      follow(runId);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  // A traced value can be linked: ?run=<id>&select=<feature or parameter id>, e.g. hole1.diameter
  useEffect(() => {
    const id = new URLSearchParams(location.search).get("select");
    const node = id ? graph?.nodes.find((n) => n.id === id) : undefined;
    if (node) {
      setSelection({ key: node.id, handles: new Set(node.sources.map((s) => s.handle).filter((h): h is string => !!h)) });
    }
  }, [graph]);

  const flags: Flag[] = useMemo(() => view?.status.results.flatMap((r) => r.flags) ?? [], [view]);
  // Values the knowledge graph confirmed are no longer open: drop them from the red marks.
  const settled = useMemo(() => {
    const ids = new Set(similar?.corroborations.filter((c) => c.status === "resolved").map((c) => c.parameter));
    const handles = new Set<string>();
    for (const n of graph?.nodes ?? []) {
      if (ids.has(n.id)) n.sources.forEach((s) => s.handle && handles.add(s.handle));
    }
    return { ids, handles };
  }, [similar, graph]);
  const flagged = useMemo(
    () =>
      new Set(
        flags
          .filter((f) => f.severity !== "info")
          .map((f) => f.target?.handle)
          .filter((h): h is string => !!h && !settled.handles.has(h)),
      ),
    [flags, settled],
  );
  const box = useMemo(() => (geometry ? sheetBox(geometry.entities) : null), [geometry]);
  const tb = geometry?.title_block ?? {};
  const runState = view ? (view.running ? "Running" : RUN_STATE_TEXT[view.status.state]) : runId ? "Starting" : "";

  const titleBlock = (
    <table className="title-block" aria-label="Title block">
      <tbody>
        <tr>
          <td colSpan={2}>
            <span>Part number</span>
            {tb.part_number?.value ?? "not read"}
          </td>
          <td>
            <span>Revision</span>
            {tb.revision?.value ?? "not read"}
          </td>
        </tr>
        <tr>
          <td>
            <span>Material</span>
            {tb.material?.value ?? "not read"}
          </td>
          <td>
            <span>Scale</span>
            {tb.scale?.value ?? "not read"}
          </td>
          <td>
            <span>Units</span>
            {geometry?.units ?? "not stated"}
          </td>
        </tr>
        <tr>
          <td colSpan={3}>
            <span>Tolerances</span>
            {tb.tolerances?.value ?? "not read"}
          </td>
        </tr>
        <tr>
          <td>
            <span>Run</span>
            {runId}
          </td>
          <td>
            <span>File version</span>
            {view?.upload?.commit.slice(0, 10) ?? ""}
          </td>
          <td className={`run-state state-${view?.status.state ?? "unknown"}`}>
            <span>Status</span>
            {runState}
          </td>
        </tr>
      </tbody>
    </table>
  );

  return (
    <div className="app">
      <header className="masthead">
        <h1>Engineering Diagram Platform</h1>
        <div className="controls">
          {samples.length > 0 && (
            <>
              <label htmlFor="sample">Sample drawing</label>
              <select id="sample" value={sample} onChange={(e) => setSample(e.target.value)}>
                {samples.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
              <button onClick={() => begin(() => api.runSample(sample))} disabled={!sample}>
                Run sample
              </button>
            </>
          )}
          <button className="secondary" onClick={() => fileInput.current?.click()}>
            Upload a drawing
          </button>
          <input
            ref={fileInput}
            type="file"
            accept=".dxf,.dwg,.pdf,.step,.stp,.stl,.igs,.iges,.png,.jpg,.jpeg,.tif,.tiff"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) begin(() => api.upload(f));
              e.target.value = "";
            }}
          />
        </div>
      </header>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      <main className="workspace">
        <Pipeline blocks={blocks} states={states} />
        <DrawingSheet
          geometry={geometry}
          box={box}
          traced={selection?.handles ?? new Set()}
          flagged={flagged}
          titleBlock={titleBlock}
          empty={
            geometry?.solids?.length ? (
              <p>
                This is a 3D model ({geometry.solids.length} solid{geometry.solids.length > 1 ? "s" : ""}). What was read
                from it is on the right; a 3D view comes later.
              </p>
            ) : runId ? (
              <p>Reading the drawing…</p>
            ) : (
              <p>Run a sample drawing or upload a DXF. The parsed drawing appears here, and any value you select is traced back to it.</p>
            )
          }
        />
        <Inspector
          geometry={geometry}
          graph={graph}
          similar={similar}
          settled={settled}
          flags={flags}
          box={box}
          view={view}
          selection={selection}
          onSelect={setSelection}
          onReview={review}
        />
      </main>

      <footer className="log" aria-label="Run events">
        <h2>Run events</h2>
        {events.length === 0 ? (
          <p className="quiet">Events appear here as each block starts and finishes.</p>
        ) : (
          <ol>
            {events.map((e) => (
              <li key={e.seq}>
                <span className="log-subject">{e.subject}</span>
                {e.payload.block && <span className="log-block">{e.payload.block}</span>}
                {e.payload.status && <span className="log-status">{e.payload.status}</span>}
              </li>
            ))}
          </ol>
        )}
      </footer>
    </div>
  );
}

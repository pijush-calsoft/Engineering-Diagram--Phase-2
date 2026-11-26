import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, watchRun } from "./api";
import { Chat } from "./components/Chat";
import { Inspector, type Selection } from "./components/Inspector";
import { Pipeline } from "./components/Pipeline";
import { type DesignResults, Results } from "./components/Results";
import { RunsList } from "./components/RunsList";
import { type Scan, Workspace } from "./components/Workspace";
import { sheetBox } from "./geometry";
import type {
  BlockInfo,
  BlockState,
  CadScript,
  ChatStatus,
  DesignGraph,
  Flag,
  Geometry,
  Margins,
  Report,
  RunEvent,
  RunSummary,
  RunView,
  SimilarParts,
  SolverRuns,
  Spend,
} from "./types";

// Stable empty values: the 3D viewer rebuilds its scene when its props change.
const NO_SOLIDS: never[] = [];
const NOTHING_TRACED = new Set<string>();
const NO_RESULTS: DesignResults = { script: null, margins: null, solverRuns: null, report: null };
const RESULT_KINDS: Record<string, keyof DesignResults> = {
  cad_script: "script",
  margins: "margins",
  solver_runs: "solverRuns",
  report: "report",
};

// three.js is large: load the 3D viewer only when a 3D model is opened.
const Viewer3D = lazy(() => import("./components/Viewer3D").then((m) => ({ default: m.Viewer3D })));

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

function money(usd: number): string {
  return usd < 0.01 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(2)}`;
}

export function App() {
  const [blocks, setBlocks] = useState<BlockInfo[]>([]);
  const [samples, setSamples] = useState<string[]>([]);
  const [sample, setSample] = useState("");
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [view, setView] = useState<RunView | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [states, setStates] = useState<Record<string, BlockState>>({});
  const [geometry, setGeometry] = useState<Geometry | null>(null);
  const [graph, setGraph] = useState<DesignGraph | null>(null);
  const [similar, setSimilar] = useState<SimilarParts | null>(null);
  const [scan, setScan] = useState<Scan | null>(null);
  const [selection, setSelection] = useState<Selection>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"read" | "check" | "ask">("read");
  const [results, setResults] = useState<DesignResults>(NO_RESULTS);
  const [previous, setPrevious] = useState<{ runId: string; margin: number; thickness: number | null } | null>(null);
  const [surface, setSurface] = useState<"drawing" | "model">("drawing");
  const [chatStatus, setChatStatus] = useState<ChatStatus | null>(null);
  const [spend, setSpend] = useState<Spend | null>(null);
  const loaded = useRef<Set<string>>(new Set());
  const stopWatch = useRef<() => void>(() => undefined);
  const fileInput = useRef<HTMLInputElement>(null);

  const refreshRuns = useCallback(() => {
    api.runs().then(setRuns).catch(() => undefined);
  }, []);
  const refreshSpend = useCallback(() => {
    api.usage().then(setSpend).catch(() => undefined);
  }, []);

  useEffect(() => {
    api.blocks().then(setBlocks).catch((e) => setError(`Cannot reach the console API: ${e.message}`));
    api.samples().then((s) => {
      setSamples(s);
      setSample(s[0] ?? "");
    });
    api.chatStatus().then(setChatStatus).catch(() => setChatStatus(null));
    refreshSpend();
    refreshRuns();
  }, [refreshRuns, refreshSpend]);

  const cite = useCallback(
    (key: string, handles: Set<string>) => setSelection((s) => (s?.key === key ? null : { key, handles })),
    [],
  );

  const refresh = useCallback(async (id: string) => {
    const v = await api.run(id);
    setView(v);
    if (v.status.state === "completed") {
      // Approving a review emits no block event: a completed run's reviewed stages are done.
      setStates((prev) => Object.fromEntries(Object.entries(prev).map(([k, s]) => [k, s === "review" ? "done" : s])));
    }
    if (v.upload?.kind === "image" && !loaded.current.has("scan")) {
      loaded.current.add("scan");
      const url = api.sourceUrl(id);
      const img = new Image();
      img.onload = () => setScan({ url, w: img.naturalWidth, h: img.naturalHeight });
      img.src = url;
    }
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
      } else if (a.kind in RESULT_KINDS && a.uri.startsWith("fabric://")) {
        loaded.current.add(a.uri);
        const doc = await api.artifact<CadScript | Margins | SolverRuns | Report>(a.uri);
        setResults((r) => ({ ...r, [RESULT_KINDS[a.kind]]: doc }) as DesignResults);
        if (a.kind === "cad_script") setTab("check"); // a model is on its way: show the design check
      }
    }
    // The run this one changed: its margin, to compare against.
    if (v.parent && !loaded.current.has("parent")) {
      loaded.current.add("parent");
      const pv = await api.run(v.parent);
      const uri = (kind: string) => pv.artifacts.find((a) => a.kind === kind && a.uri.startsWith("fabric://"))?.uri;
      const [m, s] = [uri("margins"), uri("cad_script")];
      if (m) {
        const margin = (await api.artifact<Margins>(m)).margins[0]?.margin;
        const t = s ? (await api.artifact<CadScript>(s)).parameters.find((p) => p.name === "thickness") : undefined;
        if (margin !== undefined) setPrevious({ runId: v.parent, margin, thickness: t ? Number(t.value) : null });
      }
    }
  }, []);

  const follow = useCallback(
    (id: string) => {
      stopWatch.current();
      stopWatch.current = watchRun(
        id,
        (e) => {
          setEvents((prev) => (prev.some((p) => p.seq === e.seq) ? prev : [...prev, e]));
          const s = stateFromEvent(e);
          if (s) setStates((prev) => ({ ...prev, [e.payload.block]: s }));
          if (e.subject === "run.block.completed") refresh(id);
        },
        () => {
          refresh(id);
          refreshRuns();
          refreshSpend();
        },
      );
    },
    [refresh, refreshRuns, refreshSpend],
  );

  const reset = () => {
    setError(null);
    setView(null);
    setEvents([]);
    setStates({});
    setGeometry(null);
    setGraph(null);
    setSimilar(null);
    setScan(null);
    setSelection(null);
    setResults(NO_RESULTS);
    setPrevious(null);
    setSurface("drawing");
    loaded.current = new Set();
  };

  const open = useCallback(
    (id: string) => {
      reset();
      setRunId(id);
      history.replaceState(null, "", `?run=${id}`);
      refresh(id)
        .then(() => follow(id))
        .catch((e) => setError(`Cannot open run ${id}: ${e.message}`));
    },
    [refresh, follow],
  );

  // A run can be opened by link: ?run=<id>
  useEffect(() => {
    const id = new URLSearchParams(location.search).get("run");
    if (id) open(id);
  }, [open]);

  const begin = async (start: () => Promise<{ run_id: string }>) => {
    reset();
    try {
      const { run_id } = await start();
      setRunId(run_id);
      history.replaceState(null, "", `?run=${run_id}`);
      refreshRuns();
      follow(run_id);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const rerun = (overrides: Record<string, number>) => {
    if (runId) begin(() => api.rerun(runId, overrides));
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
  const flagCounts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const r of view?.status.results ?? []) c[r.block] = r.flags.filter((f) => f.severity !== "info").length;
    return c;
  }, [view]);
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
  const box = useMemo(() => {
    if (scan) return { x0: 0, y0: 0, x1: scan.w, y1: scan.h };
    return geometry ? sheetBox(geometry.entities) : null;
  }, [geometry, scan]);
  const tb = geometry?.title_block ?? {};
  const runState = view ? (view.running ? "Running" : RUN_STATE_TEXT[view.status.state]) : runId ? "Starting" : "";
  const solids = geometry?.solids ?? [];
  const hasModel = !!view?.artifacts.some((a) => a.block === "b5_opencad" && a.kind === "step" && a.uri.startsWith("fabric://"));
  const peak = useMemo(() => results.solverRuns?.runs[0]?.max_point_mm ?? null, [results.solverRuns]);

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

  const empty = runId ? (
    <p>Reading {view?.upload?.filename ?? "the file"}…</p>
  ) : (
    <div className="welcome">
      <h2>Read a drawing</h2>
      <p>
        Run a sample or upload a DXF, DWG, PDF, scan, STEP or STL file. The platform reads it, recognises its features and
        traces every value back to where it came from.
      </p>
    </div>
  );

  return (
    <div className="app">
      <header className="masthead">
        <h1>Engineering Diagram Platform</h1>
        <div className="controls">
          {samples.length > 0 && (
            <>
              <label htmlFor="sample">Sample</label>
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
            Upload a file
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
          {spend && chatStatus?.available && (
            <span className="spend" title="Model calls logged by the Model Gateway">
              Model spend {money(spend.spent_usd)}
            </span>
          )}
        </div>
      </header>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      <Pipeline blocks={blocks} states={states} flags={flagCounts} />

      <main className="workspace">
        <RunsList runs={runs} current={runId} onOpen={open} />
        <div className="middle">
          {hasModel && runId && (
            <div className="surface-switch" role="toolbar" aria-label="Show">
              <button className="layer" aria-pressed={surface === "drawing"} onClick={() => setSurface("drawing")}>
                Drawing
              </button>
              <button className="layer" aria-pressed={surface === "model"} onClick={() => setSurface("model")}>
                Generated model
              </button>
            </div>
          )}
          {hasModel && runId && surface === "model" ? (
            <Suspense fallback={<div className="workspace-empty">Loading the 3D viewer…</div>}>
              <Viewer3D runId={runId} solids={NO_SOLIDS} traced={NOTHING_TRACED} units="mm" source="model" peak={peak} />
            </Suspense>
          ) : solids.length > 0 && runId ? (
            <Suspense fallback={<div className="workspace-empty">Loading the 3D viewer…</div>}>
              <Viewer3D runId={runId} solids={solids} traced={selection?.handles ?? new Set()} units={geometry?.units ?? null} />
            </Suspense>
          ) : (
            <Workspace
              geometry={geometry}
              graph={graph}
              box={box}
              scan={scan}
              traced={selection?.handles ?? new Set()}
              flagged={flagged}
              selectedKey={selection?.key ?? null}
              onSelect={cite}
              titleBlock={titleBlock}
              empty={empty}
            />
          )}
        </div>
        <div className="side">
          <div className="tabs" role="tablist" aria-label="Right panel">
            <button role="tab" id="tab-read" aria-selected={tab === "read"} aria-controls="panel-read" onClick={() => setTab("read")}>
              Read from the drawing
            </button>
            <button role="tab" id="tab-check" aria-selected={tab === "check"} aria-controls="panel-check" onClick={() => setTab("check")}>
              Design check
            </button>
            <button role="tab" id="tab-ask" aria-selected={tab === "ask"} aria-controls="panel-ask" onClick={() => setTab("ask")}>
              Ask about it
            </button>
          </div>
          <div role="tabpanel" id="panel-read" aria-labelledby="tab-read" hidden={tab !== "read"} className="panel">
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
          </div>
          <div role="tabpanel" id="panel-check" aria-labelledby="tab-check" hidden={tab !== "check"} className="panel">
            <Results runId={runId} view={view} results={results} previous={previous} onRerun={rerun} onReview={review} />
          </div>
          <div role="tabpanel" id="panel-ask" aria-labelledby="tab-ask" hidden={tab !== "ask"} className="panel">
            <Chat
              runId={runId}
              status={chatStatus}
              spend={spend}
              selectedKey={selection?.key ?? null}
              onCite={cite}
              onAnswered={refreshSpend}
            />
          </div>
        </div>
      </main>

      <details className="log">
        <summary>
          Run events <span className="log-count">{events.length}</span>
        </summary>
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
      </details>
    </div>
  );
}

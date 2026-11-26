import type { BlockInfo, ChatStatus, CitedAnswer, Mesh, RunEvent, RunSummary, RunView, Spend } from "./types";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : body.detail?.message;
    throw new Error(detail ?? `Request failed with status ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  blocks: () => fetch("/api/blocks").then((r) => json<BlockInfo[]>(r)),
  samples: () => fetch("/api/samples").then((r) => json<string[]>(r)),
  runSample: (name: string) =>
    fetch(`/api/runs/sample?name=${encodeURIComponent(name)}`, { method: "POST" }).then((r) =>
      json<{ run_id: string }>(r),
    ),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return fetch("/api/runs", { method: "POST", body: form }).then((r) => json<{ run_id: string }>(r));
  },
  run: (id: string) => fetch(`/api/runs/${id}`).then((r) => json<RunView>(r)),
  artifact: <T>(uri: string) => fetch(`/api/artifact?uri=${encodeURIComponent(uri)}`).then((r) => json<T>(r)),
  review: (id: string, decision: "approve" | "reject", reviewer: string) =>
    fetch(`/api/runs/${id}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision, reviewer }),
    }).then((r) => json<unknown>(r)),
  chatStatus: () => fetch("/api/chat").then((r) => json<ChatStatus>(r)),
  chat: (id: string, question: string, history: { question: string; answer: string }[], signal?: AbortSignal) =>
    fetch(`/api/runs/${id}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, history }),
      signal,
    }).then((r) => json<CitedAnswer>(r)),
  usage: () => fetch("/api/usage").then((r) => json<Spend>(r)),
  runs: () => fetch("/api/runs").then((r) => json<RunSummary[]>(r)),
  mesh: (id: string) => fetch(`/api/runs/${id}/mesh`).then((r) => json<Mesh>(r)),
  sourceUrl: (id: string) => `/api/runs/${id}/source`,
};

const SUBJECTS = ["run.planned", "run.block.started", "run.block.completed", "run.block.failed"];

/** Live run events over SSE (plan §4.3). Calls onEnd when the run stops or pauses. */
export function watchRun(id: string, onEvent: (e: RunEvent) => void, onEnd: () => void): () => void {
  const source = new EventSource(`/api/runs/${id}/events`);
  for (const subject of SUBJECTS) {
    source.addEventListener(subject, (m) => onEvent(JSON.parse((m as MessageEvent).data)));
  }
  source.addEventListener("end", () => {
    source.close();
    onEnd();
  });
  source.onerror = () => {
    source.close();
    onEnd();
  };
  return () => source.close();
}

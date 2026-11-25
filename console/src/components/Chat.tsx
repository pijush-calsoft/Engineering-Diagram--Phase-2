import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  ThreadPrimitive,
  useLocalRuntime,
  type ChatModelAdapter,
} from "@assistant-ui/react";
import { useMemo } from "react";
import { api } from "../api";
import type { ChatStatus, CitedAnswer, Spend } from "../types";

// Chat panel (plan Phase 1 console shell: "Chat panel", React + assistant-ui). Answers come from
// the Data Catalogue's cited-answer endpoint through the Model Gateway; every cited fact points
// back to the drawing.

const SUGGESTIONS = [
  "What material and tolerances does the title block give?",
  "Which values were flagged, and why?",
  "List the holes with their diameters.",
];

type Props = {
  runId: string | null;
  status: ChatStatus | null;
  spend: Spend | null;
  selectedKey: string | null;
  onCite: (key: string, handles: Set<string>) => void;
  onAnswered: () => void;
};

type Msg = { role: string; content: readonly { type: string; text?: string }[] };

function textOf(m: Msg): string {
  return m.content.map((p) => (p.type === "text" ? p.text ?? "" : "")).join("");
}

function money(usd: number | null | undefined): string {
  if (usd == null) return "cost unknown";
  return usd < 0.01 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(2)}`;
}

function adapter(runId: string, onAnswered: () => void): ChatModelAdapter {
  return {
    async run({ messages, abortSignal }) {
      const turns = messages.map((m) => ({ role: m.role, text: textOf(m as Msg) }));
      const question = turns.at(-1)?.text ?? "";
      const history = [];
      for (let i = 0; i + 1 < turns.length - 1; i += 2) {
        if (turns[i].role === "user" && turns[i + 1].role === "assistant") {
          history.push({ question: turns[i].text, answer: turns[i + 1].text });
        }
      }
      const answer = await api.chat(runId, question, history, abortSignal);
      onAnswered();
      return {
        content: [{ type: "text", text: answer.answer }],
        metadata: { custom: { answer } },
      };
    },
  };
}

function Answer({ id, answer, selectedKey, onCite }: { id: string; answer: CitedAnswer } & Pick<Props, "selectedKey" | "onCite">) {
  const review = answer.flags.filter((f) => f.severity !== "info");
  return (
    <>
      {!answer.from_facts && <p className="answer-note">Not found in what the platform read from this drawing.</p>}
      {answer.citations.length > 0 && (
        <ul className="citations" aria-label="Sources for this answer">
          {answer.citations.map((c) => {
            const key = `chat:${id}:${c.id}`;
            return (
              <li key={c.id}>
                <button
                  className={selectedKey === key ? "cite on" : "cite"}
                  aria-pressed={selectedKey === key}
                  disabled={c.handles.length === 0}
                  title={c.handles.length ? "Show on the drawing" : "This fact has no position on the drawing"}
                  onClick={() => onCite(key, new Set(c.handles))}
                >
                  <span className="cite-id">{c.id}</span>
                  {c.text}
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {review.map((f, i) => (
        <p key={i} className="answer-note">
          {f.message}
        </p>
      ))}
      <p className="answer-cost">
        {answer.input_tokens ?? "?"} + {answer.output_tokens ?? "?"} tokens, {money(answer.cost_usd)}
      </p>
    </>
  );
}

function Thread({ selectedKey, onCite }: Pick<Props, "selectedKey" | "onCite">) {
  return (
    <ThreadPrimitive.Root className="chat-thread">
      <ThreadPrimitive.Viewport className="chat-log">
        <ThreadPrimitive.Empty>
          <p className="quiet">Ask a question about this drawing. Answers use only what the platform read, and each one lists its sources.</p>
          <div className="suggestions">
            {SUGGESTIONS.map((s) => (
              <ThreadPrimitive.Suggestion key={s} prompt={s} send className="suggestion">
                {s}
              </ThreadPrimitive.Suggestion>
            ))}
          </div>
        </ThreadPrimitive.Empty>
        <ThreadPrimitive.Messages>
          {({ message }) => {
            const text = textOf(message as Msg);
            if (message.role === "user") return <p className="question">{text}</p>;
            const answer = (message.metadata?.custom as { answer?: CitedAnswer } | undefined)?.answer;
            const status = message.status;
            return (
              <div className="answer">
                {status?.type === "running" && <p className="quiet">Reading the facts…</p>}
                {status?.type === "incomplete" && (
                  <p className="answer-note">
                    {status.reason === "cancelled" ? "Stopped." : `No answer: ${String(status.error ?? "the request failed")}`}
                  </p>
                )}
                {text && <p>{text}</p>}
                {answer && <Answer id={message.id} answer={answer} selectedKey={selectedKey} onCite={onCite} />}
              </div>
            );
          }}
        </ThreadPrimitive.Messages>
      </ThreadPrimitive.Viewport>
      <ComposerPrimitive.Root className="composer">
        <ComposerPrimitive.Input className="composer-input" placeholder="Ask about this drawing" rows={2} />
        <ComposerPrimitive.Send className="composer-send">Ask</ComposerPrimitive.Send>
      </ComposerPrimitive.Root>
    </ThreadPrimitive.Root>
  );
}

function RunChat({ runId, selectedKey, onCite, onAnswered }: Omit<Props, "status" | "spend"> & { runId: string }) {
  const model = useMemo(() => adapter(runId, onAnswered), [runId, onAnswered]);
  const runtime = useLocalRuntime(model);
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <Thread selectedKey={selectedKey} onCite={onCite} />
    </AssistantRuntimeProvider>
  );
}

export function Chat({ runId, status, spend, selectedKey, onCite, onAnswered }: Props) {
  return (
    <section className="chat" aria-label="Ask about this drawing">
      {status && !status.available ? (
        <p className="quiet">{status.reason}</p>
      ) : !runId ? (
        <p className="quiet">Run a sample or upload a drawing, then ask about it here.</p>
      ) : (
        // A new run starts a new conversation.
        <RunChat key={runId} runId={runId} selectedKey={selectedKey} onCite={onCite} onAnswered={onAnswered} />
      )}
      {status?.available && (
        <p className="chat-meta">
          Answered by {status.model} through the Model Gateway. Spend so far: {money(spend?.spent_usd ?? 0)} over{" "}
          {spend?.calls ?? 0} call{spend?.calls === 1 ? "" : "s"}.
        </p>
      )}
    </section>
  );
}

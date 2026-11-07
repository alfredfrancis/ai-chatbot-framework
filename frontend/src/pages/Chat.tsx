import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { api, attachStream, sendMessage, type AgentEvent, type Chat, type Message, type ToolCall } from "../api";
import { useApp } from "../App";
import { IconArrowUp, IconCheck, IconTrash, IconX, Mark, WaveLine } from "../components/icons";

// Navigation keys whose pending message was already sent (guards against double effects).
const consumed = new Set<string>();

const SUGGESTIONS = [
  { title: "Crunch numbers", sub: "Charts from any CSV", prompt: "Look at the files in my workspace and summarise any spreadsheets you find." },
  { title: "Automate a chore", sub: "Runs on a schedule", prompt: "Help me set up a task that runs every weekday morning." },
  { title: "Learn a skill", sub: "Teach it once, reuse forever", prompt: "Make a skill for writing my weekly status update." },
];

function describe(call: ToolCall): { verb: string; detail: string; mono: boolean } {
  const a = call.arguments as Record<string, string>;
  switch (call.name) {
    case "bash": return { verb: "Ran", detail: a.command ?? "", mono: true };
    case "write": return { verb: "Wrote", detail: a.path ?? "", mono: true };
    case "edit": return { verb: "Edited", detail: a.path ?? "", mono: true };
    case "read": {
      const p = a.path ?? "";
      const m = p.match(/^skills\/([^/]+)\/SKILL\.md$/);
      return m ? { verb: "Used skill", detail: m[1], mono: false } : { verb: "Read", detail: p, mono: true };
    }
  }
  const m = call.name.match(/^mcp__(.+?)__(.+)$/);
  if (m) return { verb: "Used", detail: `${m[1]} · ${m[2]}`, mono: false };
  return { verb: "Used", detail: call.name, mono: false };
}

const secs = (ms: number | null | undefined) => (ms == null ? "" : `${(ms / 1000).toFixed(1)}s`);

function Step({ call, result, running }: { call: ToolCall; result?: Message; running: boolean }) {
  const [open, setOpen] = useState(false);
  const d = describe(call);
  return (
    <>
      <button className="step" onClick={() => result && setOpen(!open)} aria-expanded={open} data-testid="tool-step">
        {result ? (
          <span className={result.is_error ? "fail" : "ok"}>{result.is_error ? <IconX /> : <IconCheck />}</span>
        ) : running ? <span className="spinner" aria-label="Working" /> : <span className="fail"><IconX /></span>}
        <span className="lbl">{d.verb} <span className={d.mono ? "mono" : ""} style={{ fontWeight: d.mono ? 400 : 600 }}>{d.detail}</span></span>
        <span className="time">{result ? secs(result.duration_ms) : ""}</span>
      </button>
      {open && result && <pre className="step-output">{result.content}</pre>}
    </>
  );
}

type Block = { kind: "text"; id: number; text: string } | { kind: "activity"; id: number; calls: ToolCall[] };
type Item = { kind: "user"; msg: Message } | { kind: "turn"; id: number; blocks: Block[] } | { kind: "summary"; id: number };

/** Group messages into user bubbles and agent turns; consecutive tool calls share one activity card. */
function group(messages: Message[]): Item[] {
  const items: Item[] = [];
  for (const m of messages) {
    if (m.role === "user") { items.push({ kind: "user", msg: m }); continue; }
    if ((m.role as string) === "summary") { items.push({ kind: "summary", id: m.id }); continue; }
    if (m.role !== "assistant") continue;
    let turn = items[items.length - 1];
    if (!turn || turn.kind !== "turn") { turn = { kind: "turn", id: m.id, blocks: [] }; items.push(turn); }
    if (m.content) turn.blocks.push({ kind: "text", id: m.id, text: m.content });
    if (m.tool_calls.length) {
      const last = turn.blocks[turn.blocks.length - 1];
      if (last && last.kind === "activity") last.calls.push(...m.tool_calls);
      else turn.blocks.push({ kind: "activity", id: m.id, calls: [...m.tool_calls] });
    }
  }
  return items;
}

function Thread({ messages, running, queued, notices }: { messages: Message[]; running: boolean; queued: string[]; notices: string[] }) {
  const results = new Map(messages.filter((m) => m.role === "tool").map((m) => [m.tool_call_id, m]));
  const items = group(messages);
  const toolBusy = running && messages.some((m) => m.role === "assistant" && m.tool_calls.some((c) => !results.has(c.id)));
  const lastItem = items[items.length - 1];
  const working = <div className="working" aria-label="Working"><WaveLine />Working…</div>;
  return (
    <div className="thread">
      {items.map((it) => {
        if (it.kind === "user") return <div key={it.msg.id} className="bubble" data-testid="user-msg">{it.msg.content}</div>;
        if (it.kind === "summary") return <div key={it.id} className="notice">Earlier messages were summarised to keep things fast.</div>;
        const live = running && it === lastItem;
        return (
          <div key={it.id} className="turn">
            <Mark live={live} />
            <div className="body">
              {it.blocks.map((b) => b.kind === "text" ? (
                <div key={`t${b.id}`} className="assistant" data-testid="assistant-msg"><Markdown remarkPlugins={[remarkGfm]}>{b.text}</Markdown></div>
              ) : (
                <div key={`a${b.id}`} className="activity" data-testid="activity">
                  {b.calls.map((c) => <Step key={c.id} call={c} result={results.get(c.id)} running={running} />)}
                </div>
              ))}
              {live && !toolBusy && working}
            </div>
          </div>
        );
      })}
      {running && lastItem?.kind !== "turn" && <div className="turn"><Mark live /><div className="body">{working}</div></div>}
      {queued.map((q, i) => (
        <div key={`q${i}`} className="stack" style={{ alignItems: "flex-end", gap: 4 }}>
          <div className="bubble queued" data-testid="queued-msg">{q}</div>
          <span className="hint">Queued — I'll read this next</span>
        </div>
      ))}
      {notices.map((n, i) => <div key={`n${i}`} className="notice">{n}</div>)}
    </div>
  );
}

function Composer({ onSend, onStop, running, placeholder }: {
  onSend: (t: string) => void; onStop?: () => void; running: boolean; placeholder?: string;
}) {
  const [text, setText] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => { ref.current?.focus(); }, []);
  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    const t = text.trim();
    if (!t) return;
    setText("");
    if (ref.current) ref.current.style.height = "auto";
    onSend(t);
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(); }
  };
  const showStop = running && !text.trim() && onStop;
  return (
    <form className="composer" onSubmit={submit}>
      <label htmlFor="composer" className="sr-only">Message</label>
      <textarea id="composer" ref={ref} rows={1} value={text} onKeyDown={onKey}
        placeholder={running ? "Add to the conversation…" : placeholder ?? "Ask anything"}
        onChange={(e) => { setText(e.target.value); e.target.style.height = "auto"; e.target.style.height = `${e.target.scrollHeight}px`; }} />
      {showStop ? (
        <button className="send" type="button" aria-label="Stop" onClick={onStop}><span className="stop-square" /></button>
      ) : (
        <button className="send" type="submit" aria-label="Send" disabled={!text.trim()}><IconArrowUp /></button>
      )}
    </form>
  );
}

function Home({ onStart }: { onStart: (t: string) => void }) {
  const [status, setStatus] = useState("");
  useEffect(() => {
    Promise.all([
      api.get<{ kind: string }>("/sandbox").catch(() => null),
      api.get<unknown[]>("/skills").catch(() => []),
      api.get<{ config: string }>("/mcp/config").catch(() => ({ config: "{}" })),
    ]).then(([sbx, skills, mcp]) => {
      let servers = 0;
      try { servers = Object.keys(JSON.parse(mcp.config).mcpServers ?? {}).length; } catch { /* ignore */ }
      const box = sbx?.kind === "local" ? "Local sandbox" : "Sandbox ready";
      setStatus(`${box} · ${skills.length} skill${skills.length === 1 ? "" : "s"} · ${servers} connection${servers === 1 ? "" : "s"}`);
    });
  }, []);
  return (
    <div className="home">
      {status && <span className="pill" data-testid="status-pill"><span className="dot" />{status}</span>}
      <h1>What can I take off your plate today?</h1>
      <Composer onSend={onStart} running={false} placeholder="Ask anything, or describe a job to do…" />
      <div className="suggestions">
        {SUGGESTIONS.map((s) => (
          <button key={s.title} className="suggestion" onClick={() => onStart(s.prompt)}>
            <div className="title">{s.title}</div>
            <div className="sub">{s.sub}</div>
          </button>
        ))}
      </div>
    </div>
  );
}

export default function ChatPage() {
  const { id } = useParams();
  const chatId = id ? Number(id) : null;
  const navigate = useNavigate();
  const location = useLocation();
  const { refreshChats } = useApp();
  const [chat, setChat] = useState<Chat | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [running, setRunning] = useState(false);
  const [queued, setQueued] = useState<string[]>([]);
  const [notices, setNotices] = useState<string[]>([]);
  const [error, setError] = useState("");
  const scroller = useRef<HTMLDivElement>(null);

  const apply = useCallback((e: AgentEvent) => {
    if (e.type === "done") { setRunning(false); return; }
    setRunning(true);
    if (e.type === "message") {
      setMessages((prev) => (prev.some((m) => m.id === e.message.id) ? prev : [...prev, e.message]));
      if (e.message.role === "user") {
        setQueued((q) => { const i = q.indexOf(e.message.content); return i < 0 ? q : [...q.slice(0, i), ...q.slice(i + 1)]; });
      }
    } else if (e.type === "notice") setNotices((n) => [...n, e.text]);
    else if (e.type === "error") setError(e.error);
    else if (e.type === "stopped") setNotices((n) => [...n, "Stopped."]);
  }, []);

  const load = useCallback(async () => {
    if (!chatId) return null;
    try {
      const c = await api.get<Chat>(`/chats/${chatId}`);
      setChat(c);
      setMessages(c.messages);
      return c;
    } catch {
      navigate("/", { replace: true });
      return null;
    }
  }, [chatId, navigate]);

  const finish = useCallback(() => { setRunning(false); setQueued([]); refreshChats(); load(); }, [refreshChats, load]);

  const send = async (content: string, target: number) => {
    setError("");
    if (running) setQueued((q) => [...q, content]);
    else { setRunning(true); setNotices([]); }
    const how = await sendMessage(target, content, apply).catch((err) => { setError(String(err)); return "streamed" as const; });
    if (how === "streamed") finish();
  };

  useEffect(() => {
    setChat(null); setMessages([]); setError(""); setNotices([]); setQueued([]); setRunning(false);
    if (!chatId) return;
    const pending = (location.state as { pending?: string } | null)?.pending;
    if (pending && !consumed.has(location.key)) {
      consumed.add(location.key);
      navigate(location.pathname, { replace: true, state: null });
      load().then(() => send(pending, chatId));
    } else if (!pending) {
      load().then((c) => { if (c?.running) { setRunning(true); attachStream(chatId, apply).then(finish); } });
    }
  }, [chatId]); // eslint-disable-line

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [messages, running, queued]);

  const start = async (content: string) => {
    const c = await api.post<{ id: number }>("/chats", {});
    refreshChats();
    navigate(`/c/${c.id}`, { state: { pending: content } });
  };
  const stop = () => { if (chatId) api.post(`/chats/${chatId}/stop`); };
  const remove = async () => {
    if (!chatId || !confirm("Delete this chat?")) return;
    await api.del(`/chats/${chatId}`);
    refreshChats();
    navigate("/");
  };

  if (!chatId) return <Home onStart={start} />;

  return (
    <>
      <header className="chat-header">
        <span className="t">{chat?.title && chat.title !== "New chat" ? chat.title : (messages.find((m) => m.role === "user")?.content.split("\n")[0].slice(0, 60) ?? "")}</span>
        <span className="actions"><button className="icon-btn" aria-label="Delete chat" title="Delete chat" onClick={remove}><IconTrash /></button></span>
      </header>
      <div className="chat-scroll" ref={scroller}>
        <Thread messages={messages} running={running} queued={queued} notices={notices} />
        {error && <div className="thread" style={{ marginTop: 16 }}><div className="banner" role="alert">{error}</div></div>}
      </div>
      <div className="composer-wrap">
        <Composer key={chatId} onSend={(t) => send(t, chatId)} onStop={stop} running={running} />
        <div className="footnote">Works in a private sandbox only you can see. It can make mistakes.</div>
      </div>
    </>
  );
}

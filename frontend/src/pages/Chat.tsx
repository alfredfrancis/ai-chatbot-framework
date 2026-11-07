import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { api, attachStream, sendMessage, type AgentEvent, type Chat, type Message, type ToolCall } from "../api";
import { Topbar, useApp } from "../App";
import { IconArrowUp, IconCheck, IconClock, IconDrawer, IconSpark, IconTrash, IconX, Keys, Mark } from "../components/icons";

// Navigation keys whose pending message was already sent (guards against double effects).
const consumed = new Set<string>();

const TRY: { icon: ReactNode; text: string; prompt: string }[] = [
  { icon: <IconDrawer />, text: "Summarise the spreadsheets in my files", prompt: "Look at the files in my workspace and summarise any spreadsheets you find." },
  { icon: <IconClock />, text: "Every weekday at 8:00, write my plan for the day", prompt: "Help me set up a task that writes my plan for the day every weekday at 8:00." },
  { icon: <IconSpark />, text: "Turn how I write my weekly update into a skill", prompt: "Make a skill for writing my weekly status update." },
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
        <span className={`state${result ? (result.is_error ? " fail" : " ok") : running ? "" : " fail"}`}>
          {result ? (result.is_error ? <IconX /> : <IconCheck />) : running ? <span className="spin" aria-label="Working" /> : <IconX />}
        </span>
        <span className="verb">{d.verb}</span>{" "}
        <span className={`detail${d.mono ? "" : " name"}`}>{d.detail}</span>
        {" "}<span className="time">{result ? secs(result.duration_ms) : ""}</span>
      </button>
      {open && result && <pre className="step-output">{result.content}</pre>}
    </>
  );
}

type Block = { kind: "text"; id: number; text: string } | { kind: "steps"; id: number; calls: ToolCall[] };
type Item = { kind: "user"; msg: Message } | { kind: "turn"; id: number; blocks: Block[] } | { kind: "summary"; id: number };

/** User messages, and agent turns where consecutive tool calls share one steps card. */
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
      if (last && last.kind === "steps") last.calls.push(...m.tool_calls);
      else turn.blocks.push({ kind: "steps", id: m.id, calls: [...m.tool_calls] });
    }
  }
  return items;
}

function Thread({ messages, running, queued, notices }: { messages: Message[]; running: boolean; queued: string[]; notices: string[] }) {
  const results = new Map(messages.filter((m) => m.role === "tool").map((m) => [m.tool_call_id, m]));
  const items = group(messages);
  const toolBusy = running && messages.some((m) => m.role === "assistant" && m.tool_calls.some((c) => !results.has(c.id)));
  const last = items[items.length - 1];
  const working = <div className="working" aria-label="Working">Working…</div>;
  return (
    <div className="thread">
      {items.map((it) => {
        if (it.kind === "user") return <div key={it.msg.id} className="user-msg" data-testid="user-msg">{it.msg.content}</div>;
        if (it.kind === "summary") return <div key={it.id} className="notice">Earlier messages were summarised to keep things fast.</div>;
        const live = running && it === last;
        return (
          <div key={it.id} className="turn">
            <Mark size={24} live={live} />
            <div className="body">
              {it.blocks.map((b) => b.kind === "text" ? (
                <div key={`t${b.id}`} className="answer" data-testid="assistant-msg"><Markdown remarkPlugins={[remarkGfm]}>{b.text}</Markdown></div>
              ) : (
                <div key={`s${b.id}`} className="steps" data-testid="activity">
                  {b.calls.map((c) => <Step key={c.id} call={c} result={results.get(c.id)} running={running} />)}
                </div>
              ))}
              {live && !toolBusy && working}
            </div>
          </div>
        );
      })}
      {running && last?.kind !== "turn" && <div className="turn"><Mark size={24} live /><div className="body">{working}</div></div>}
      {queued.map((q, i) => (
        <div key={`q${i}`} className="queued">
          <div className="user-msg" data-testid="queued-msg">{q}</div>
          <span className="hint">Queued · read at the next step</span>
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
    if (e.key === "Escape" && running && onStop) { e.preventDefault(); onStop(); }
  };
  const showStop = running && !text.trim() && onStop;
  return (
    <form className="composer" onSubmit={submit}>
      <label htmlFor="composer" className="sr-only">Message</label>
      <textarea id="composer" ref={ref} rows={1} value={text} onKeyDown={onKey}
        placeholder={running ? "Add to the conversation…" : placeholder ?? "Ask anything"}
        onChange={(e) => { setText(e.target.value); e.target.style.height = "auto"; e.target.style.height = `${e.target.scrollHeight}px`; }} />
      <div className="bar">
        <span className="hints row-flex">
          {running ? <>Messages you send now are read at the next step · <Keys keys={["Esc"]} /> stop</>
            : <><Keys keys={["↵"]} /> send <Keys keys={["⇧", "↵"]} /> new line</>}
        </span>
        {showStop ? (
          <button className="send stop" type="button" aria-label="Stop" onClick={onStop}><span className="square" /></button>
        ) : (
          <button className="send" type="submit" aria-label="Send" disabled={!text.trim()}><IconArrowUp /></button>
        )}
      </div>
    </form>
  );
}

function greeting(name: string) {
  const h = new Date().getHours();
  const part = h < 5 ? "Good evening" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  return `${part}, ${name}.`;
}

function Home({ onStart }: { onStart: (t: string) => void }) {
  const { user, counts } = useApp();
  const n = (x: number, one: string) => `${x} ${one}${x === 1 ? "" : "s"}`;
  return (
    <>
      <Topbar title="New chat" />
      <div className="home">
        <div>
          <h1>{greeting(user.name || "there")}</h1>
          <p className="sub" data-testid="status-line">
            Your agent has a private computer, {n(counts.files, "file")}, {n(counts.skills, "skill")} and {n(counts.connections, "connection")}.
          </p>
        </div>
        <Composer onSend={onStart} running={false} placeholder="Ask anything, or describe a job to do" />
        <div className="try">
          <div className="label-row">Try</div>
          {TRY.map((t) => <button key={t.text} onClick={() => onStart(t.prompt)}>{t.icon}{t.text}</button>)}
        </div>
      </div>
    </>
  );
}

export default function ChatPage() {
  const { id } = useParams();
  const chatId = id ? Number(id) : null;
  const navigate = useNavigate();
  const location = useLocation();
  const { refresh } = useApp();
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
        refresh(); // the chat's title is set from its first message
        setQueued((q) => { const i = q.indexOf(e.message.content); return i < 0 ? q : [...q.slice(0, i), ...q.slice(i + 1)]; });
      }
    } else if (e.type === "notice") setNotices((n) => [...n, e.text]);
    else if (e.type === "error") setError(e.error);
    else if (e.type === "stopped") setNotices((n) => [...n, "Stopped."]);
  }, [refresh]);

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

  const finish = useCallback(() => { setRunning(false); setQueued([]); refresh(); load(); }, [refresh, load]);

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
    refresh();
    navigate(`/c/${c.id}`, { state: { pending: content } });
  };
  const stop = () => { if (chatId) api.post(`/chats/${chatId}/stop`); };
  const [confirming, setConfirming] = useState(false);
  const remove = async () => {
    if (!chatId) return;
    if (!confirming) { setConfirming(true); setTimeout(() => setConfirming(false), 4000); return; }
    await api.del(`/chats/${chatId}`);
    refresh();
    navigate("/");
  };

  if (!chatId) return <Home onStart={start} />;
  const title = chat?.title && chat.title !== "New chat" ? chat.title : (messages.find((m) => m.role === "user")?.content.split("\n")[0].slice(0, 60) ?? "");

  return (
    <>
      <Topbar crumb="Chats" title={title}>
        {running && <span className="badge success">Working</span>}
        <button className={`btn ${confirming ? "danger" : "ghost"} ${confirming ? "sm" : "icon"}`} aria-label={confirming ? "Confirm delete" : "Delete chat"}
          title="Delete chat" onClick={remove}>{confirming ? "Delete chat?" : <IconTrash />}</button>
      </Topbar>
      <div className="chat-scroll" ref={scroller}>
        <Thread messages={messages} running={running} queued={queued} notices={notices} />
        {error && <div className="thread" style={{ marginTop: 16 }}><div className="banner" role="alert">{error}</div></div>}
      </div>
      <div className="composer-wrap">
        <Composer key={chatId} onSend={(t) => send(t, chatId)} onStop={stop} running={running} />
      </div>
    </>
  );
}

import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { api, streamMessage, type AgentEvent, type Chat, type Message, type ToolCall } from "../api";
import { useApp } from "../App";
import { IconArrowUp, IconCheck, IconTrash, IconX } from "../components/icons";

// Navigation keys whose pending message was already sent (guards against double effects).
const consumed = new Set<string>();

const SUGGESTIONS = [
  { title: "Plan my week", sub: "Turn a messy to-do list into a schedule" },
  { title: "Analyse a spreadsheet", sub: "Upload a CSV to your workspace and ask" },
  { title: "Remember something", sub: "“Remember that I prefer short answers”" },
  { title: "Write a small script", sub: "Harbor can run code in its sandbox" },
];

function describeCall(call: ToolCall): { verb: string; detail: string; mono: boolean } {
  const a = call.arguments as Record<string, string>;
  switch (call.name) {
    case "run_command": return { verb: "Ran", detail: a.command ?? "", mono: true };
    case "write_file": return { verb: "Wrote", detail: a.path ?? "", mono: true };
    case "read_file": return { verb: "Read", detail: a.path ?? "", mono: true };
    case "list_files": return { verb: "Looked at", detail: "workspace files", mono: false };
    case "remember": return { verb: "Remembered", detail: a.fact ?? "", mono: false };
  }
  const m = call.name.match(/^mcp__(.+?)__(.+)$/);
  if (m) return { verb: "Used", detail: `${m[1]} · ${m[2]}`, mono: false };
  return { verb: "Used", detail: call.name, mono: false };
}

function ToolChip({ call, result, running }: { call: ToolCall; result?: Message; running: boolean }) {
  const [open, setOpen] = useState(false);
  const d = describeCall(call);
  return (
    <>
      <button className="chip" onClick={() => result && setOpen(!open)} aria-expanded={open} data-testid="tool-chip">
        {result ? (
          <span style={{ color: result.is_error ? "var(--danger)" : "var(--success)", display: "flex" }}>
            {result.is_error ? <IconX /> : <IconCheck />}
          </span>
        ) : running ? <span className="spinner" aria-label="Working" /> : null}
        <span className="lbl">
          {d.verb} <span className={d.mono ? "mono" : ""} style={{ fontWeight: d.mono ? 400 : 600 }}>{d.detail}</span>
        </span>
      </button>
      {open && result && <pre className="chip-output">{result.content}</pre>}
    </>
  );
}

function Thread({ messages, running, notices }: { messages: Message[]; running: boolean; notices: string[] }) {
  const results = new Map(messages.filter((m) => m.role === "tool").map((m) => [m.tool_call_id, m]));
  const last = messages[messages.length - 1];
  const waiting = running && (!last || last.role !== "assistant" || last.tool_calls.length === 0 || last.tool_calls.every((c) => results.has(c.id)));
  return (
    <div className="thread">
      {messages.map((m) => {
        if (m.role === "user") return <div key={m.id} className="bubble" data-testid="user-msg">{m.content}</div>;
        if (m.role !== "assistant") return null;
        return (
          <div key={m.id} className="stack" style={{ gap: 8 }}>
            {m.content && (
              <div className="assistant" data-testid="assistant-msg">
                <Markdown remarkPlugins={[remarkGfm]}>{m.content}</Markdown>
              </div>
            )}
            {m.tool_calls.length > 0 && (
              <div className="chips">
                {m.tool_calls.map((c) => <ToolChip key={c.id} call={c} result={results.get(c.id)} running={running} />)}
              </div>
            )}
          </div>
        );
      })}
      {notices.map((n, i) => <div key={i} className="notice">{n}</div>)}
      {waiting && <div className="typing" aria-label="Harbor is thinking"><span /><span /><span /></div>}
    </div>
  );
}

export default function ChatPage() {
  const { id } = useParams();
  const chatId = id ? Number(id) : null;
  const navigate = useNavigate();
  const location = useLocation();
  const { user, refreshChats } = useApp();
  const [chat, setChat] = useState<Chat | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [running, setRunning] = useState(false);
  const [notices, setNotices] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [text, setText] = useState("");
  const scroller = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);

  const load = useCallback(async () => {
    if (!chatId) return;
    try {
      const c = await api.get<Chat>(`/chats/${chatId}`);
      setChat(c);
      setMessages(c.messages);
      return c;
    } catch {
      navigate("/", { replace: true });
    }
  }, [chatId, navigate]);

  const send = useCallback(async (content: string, target: number) => {
    setRunning(true);
    setError("");
    setNotices([]);
    await streamMessage(target, content, (e: AgentEvent) => {
      if (e.type === "message") setMessages((prev) => [...prev, e.message]);
      else if (e.type === "notice") setNotices((n) => [...n, e.text]);
      else if (e.type === "error") setError(e.error);
      else if (e.type === "done") setRunning(false);
    }).catch((err) => setError(String(err)));
    setRunning(false);
    refreshChats();
    load();
  }, [refreshChats, load]);

  // Load the chat, and send a message handed over from the new-chat screen.
  useEffect(() => {
    setChat(null);
    setMessages([]);
    setError("");
    setNotices([]);
    if (!chatId) return;
    const pending = (location.state as { pending?: string } | null)?.pending;
    if (pending && !consumed.has(location.key)) {
      consumed.add(location.key);
      navigate(location.pathname, { replace: true, state: null });
      load().then(() => send(pending, chatId));
    } else if (!pending) {
      load();
    }
    input.current?.focus();
  }, [chatId]);

  // A scheduled task may still be running in this chat: poll until it is done.
  useEffect(() => {
    if (!chat?.running || running) return;
    const t = setInterval(async () => {
      const c = await load();
      if (c && !c.running) clearInterval(t);
    }, 1500);
    return () => clearInterval(t);
  }, [chat?.running, running, load]);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [messages, running]);

  const submit = async (e?: FormEvent) => {
    e?.preventDefault();
    const content = text.trim();
    if (!content || running) return;
    setText("");
    if (!chatId) {
      const c = await api.post<{ id: number }>("/chats", {});
      refreshChats();
      navigate(`/c/${c.id}`, { state: { pending: content } });
      return;
    }
    send(content, chatId);
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  const remove = async () => {
    if (!chatId || !confirm("Delete this chat?")) return;
    await api.del(`/chats/${chatId}`);
    refreshChats();
    navigate("/");
  };

  const firstName = user.name || "there";
  const busy = running || !!chat?.running;

  return (
    <>
      {chatId ? (
        <>
          <header className="chat-header">
            <span className="t">{chat?.title ?? ""}</span>
            <span className="actions">
              <button className="icon-btn" aria-label="Delete chat" title="Delete chat" onClick={remove}><IconTrash /></button>
            </span>
          </header>
          <div className="chat-scroll" ref={scroller}>
            <Thread messages={messages} running={busy} notices={notices} />
            {error && <div className="thread" style={{ marginTop: 16 }}><div className="banner" role="alert">{error}</div></div>}
          </div>
        </>
      ) : (
        <div className="welcome">
          <h1>Hi {firstName}. What can I do for you?</h1>
          <div className="suggestions">
            {SUGGESTIONS.map((s) => (
              <button key={s.title} className="suggestion" onClick={() => { setText(s.sub.replace(/[“”]/g, "")); input.current?.focus(); }}>
                <div className="title">{s.title}</div>
                <div className="sub">{s.sub}</div>
              </button>
            ))}
          </div>
        </div>
      )}
      <div className="composer-wrap">
        <form className="composer" onSubmit={submit}>
          <label htmlFor="composer" className="sr-only">Message</label>
          <textarea
            id="composer" ref={input} rows={1} placeholder="Ask anything" value={text}
            onChange={(e) => { setText(e.target.value); e.target.style.height = "auto"; e.target.style.height = `${e.target.scrollHeight}px`; }}
            onKeyDown={onKey} autoFocus
          />
          <button className="send" type="submit" aria-label="Send" disabled={!text.trim() || busy}><IconArrowUp /></button>
        </form>
        <div className="footnote">Harbor can make mistakes. It works in a private sandbox that only you can see.</div>
      </div>
    </>
  );
}

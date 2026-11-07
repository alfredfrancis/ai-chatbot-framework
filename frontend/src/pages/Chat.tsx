import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { acp, cancel, loadSession, newSession, prompt, WORKSPACE_URI, type AcpNotification, type Attachment, type SessionUpdate, type ToolStatus } from "../acp";
import { api, uploadFile, type ChatSummary } from "../api";
import { Topbar, useApp } from "../App";
import { IconArrowUp, IconCheck, IconClock, IconDrawer, IconFile, IconPaperclip, IconSpark, IconTrash, IconX, Keys, Mark } from "../components/icons";

// Navigation keys whose pending message was already sent (guards against double effects).
const consumed = new Set<string>();

const TRY: { icon: ReactNode; text: string; prompt: string }[] = [
  { icon: <IconDrawer />, text: "Summarise the spreadsheets in my files", prompt: "Look at the files in my workspace and summarise any spreadsheets you find." },
  { icon: <IconClock />, text: "Every weekday at 8:00, write my plan for the day", prompt: "Help me set up a task that writes my plan for the day every weekday at 8:00." },
  { icon: <IconSpark />, text: "Turn how I write my weekly update into a skill", prompt: "Make a skill for writing my weekly status update." },
];

/** A tool call as the chat knows it from ACP tool_call / tool_call_update notifications. */
type ToolCall = { id: string; title: string; tool?: string; input: Record<string, unknown>; status: ToolStatus; output?: string; durationMs?: number | null };
type Entry =
  | { kind: "user"; key: string; text: string; files: Attachment[]; messageId?: number | string }
  | { kind: "text"; key: string; text: string; messageId?: number | string }
  | { kind: "tool"; key: string; call: ToolCall }
  | { kind: "notice"; key: string; text: string };

let keySeq = 0;
const nextKey = () => `e${keySeq++}`;
const textOf = (c: unknown) => (c && typeof c === "object" && (c as { type?: string }).type === "text" ? String((c as { text?: unknown }).text ?? "") : "");
/** A resource_link to a workspace file (an attachment), or null. */
const fileOf = (c: unknown): Attachment | null => {
  const b = c as { type?: string; uri?: unknown; name?: unknown } | null;
  if (!b || b.type !== "resource_link" || typeof b.uri !== "string" || !b.uri.startsWith(WORKSPACE_URI)) return null;
  return { uri: b.uri, name: String(b.name ?? b.uri.split("/").pop()) };
};
/** file:///workspace/<path>, encoded as the agent stores it (brackets too, so the link stays one token). */
const fileUri = (path: string) =>
  WORKSPACE_URI + path.split("/").map((p) => encodeURIComponent(p).replace(/\(/g, "%28").replace(/\)/g, "%29")).join("/");
/** Path of an attachment inside the workspace, for the file links. */
const pathOf = (f: Attachment) => decodeURIComponent(f.uri.slice(WORKSPACE_URI.length));
/** One message the user sent: what the queue shows and how its echo is recognised. */
type Outgoing = { text: string; files: Attachment[] };

/** Apply one ACP session update to the chat's entries. Replays and live updates go through the same path. */
function reduce(entries: Entry[], u: SessionUpdate): Entry[] {
  const messageId = u._meta?.acf?.messageId;
  switch (u.sessionUpdate) {
    case "user_message_chunk":
    case "agent_message_chunk": {
      const content = (u as { content: unknown }).content;
      const text = textOf(content);
      if (u.sessionUpdate === "user_message_chunk") {
        // A user message arrives as a text chunk and then one resource_link chunk per attached file.
        const file = fileOf(content);
        const i = messageId == null ? -1 : entries.findIndex((e) => e.kind === "user" && e.messageId === messageId);
        if (i >= 0) {
          const e = entries[i] as Extract<Entry, { kind: "user" }>;
          if (!file || e.files.some((f) => f.uri === file.uri)) return entries; // already shown (a repeated replay)
          return entries.map((x, j) => (j === i ? { ...e, files: [...e.files, file] } : x));
        }
        return [...entries, { kind: "user", key: nextKey(), text, files: file ? [file] : [], messageId }];
      }
      if (messageId != null && entries.some((e) => e.kind === "text" && e.messageId === messageId)) {
        const last = entries[entries.length - 1];
        if (last.kind === "text" && last.messageId === messageId) return [...entries.slice(0, -1), { ...last, text: last.text + text }];
        return entries; // already shown (a repeated replay)
      }
      return [...entries, { kind: "text", key: nextKey(), text, messageId }];
    }
    case "tool_call": {
      const t = u as Extract<SessionUpdate, { sessionUpdate: "tool_call" }>;
      if (entries.some((e) => e.kind === "tool" && e.call.id === t.toolCallId)) return entries;
      const call: ToolCall = { id: t.toolCallId, title: t.title, tool: t._meta?.acf?.tool, input: t.rawInput ?? {}, status: t.status ?? "pending" };
      return [...entries, { kind: "tool", key: nextKey(), call }];
    }
    case "tool_call_update": {
      const t = u as Extract<SessionUpdate, { sessionUpdate: "tool_call_update" }>;
      return entries.map((e) => {
        if (e.kind !== "tool" || e.call.id !== t.toolCallId) return e;
        const output = t.content ? t.content.map((c) => textOf(c.content)).join("\n") : e.call.output;
        const durationMs = t._meta?.acf?.durationMs ?? e.call.durationMs;
        return { ...e, call: { ...e.call, status: t.status ?? e.call.status, title: t.title ?? e.call.title, output, durationMs } };
      });
    }
  }
  return entries;
}

function describe(call: ToolCall): { verb: string; detail: string; mono: boolean } {
  const a = call.input as Record<string, string>;
  switch (call.tool) {
    case "bash": return { verb: "Ran", detail: a.command ?? "", mono: true };
    case "write": return { verb: "Wrote", detail: a.path ?? "", mono: true };
    case "edit": return { verb: "Edited", detail: a.path ?? "", mono: true };
    case "read": {
      const p = a.path ?? "";
      const m = p.match(/^skills\/([^/]+)\/SKILL\.md$/);
      return m ? { verb: "Used skill", detail: m[1], mono: false } : { verb: "Read", detail: p, mono: true };
    }
    case "mcp_call": return { verb: "Used", detail: `${a.server} · ${a.tool}`, mono: false };
  }
  const m = call.tool?.match(/^mcp__(.+?)__(.+)$/);
  if (m) return { verb: "Used", detail: `${m[1]} · ${m[2]}`, mono: false };
  const [verb, ...rest] = call.title.split(" ");
  return { verb, detail: rest.join(" "), mono: false };
}

const secs = (ms: number | null | undefined) => (ms == null ? "" : `${(ms / 1000).toFixed(1)}s`);

function Step({ call, running }: { call: ToolCall; running: boolean }) {
  const [open, setOpen] = useState(false);
  const d = describe(call);
  const finished = call.status === "completed" || call.status === "failed";
  const failed = call.status === "failed" || (!finished && !running);
  return (
    <>
      <button className="step" onClick={() => finished && setOpen(!open)} aria-expanded={open} data-testid="tool-step">
        <span className={`state${finished ? (failed ? " fail" : " ok") : running ? "" : " fail"}`}>
          {finished ? (failed ? <IconX /> : <IconCheck />) : running ? <span className="spin" aria-label="Working" /> : <IconX />}
        </span>
        <span className="verb">{d.verb}</span>{" "}
        <span className={`detail${d.mono ? "" : " name"}`}>{d.detail}</span>
        {" "}<span className="time">{finished ? secs(call.durationMs) : ""}</span>
      </button>
      {open && finished && <pre className="step-output">{call.output}</pre>}
    </>
  );
}

type Block = { kind: "text"; key: string; text: string } | { kind: "steps"; key: string; calls: ToolCall[] };
type Item = { kind: "user"; key: string; text: string; files: Attachment[] } | { kind: "notice"; key: string; text: string } | { kind: "turn"; key: string; blocks: Block[] };

/** User messages, notices, and agent turns where consecutive tool calls share one steps card. */
function group(entries: Entry[]): Item[] {
  const items: Item[] = [];
  for (const e of entries) {
    if (e.kind === "user") { items.push({ kind: "user", key: e.key, text: e.text, files: e.files }); continue; }
    if (e.kind === "notice") { items.push({ kind: "notice", key: e.key, text: e.text }); continue; }
    let turn = items[items.length - 1];
    if (!turn || turn.kind !== "turn") { turn = { kind: "turn", key: e.key, blocks: [] }; items.push(turn); }
    const last = turn.blocks[turn.blocks.length - 1];
    if (e.kind === "text") { if (e.text) turn.blocks.push({ kind: "text", key: e.key, text: e.text }); }
    else if (last && last.kind === "steps") last.calls.push(e.call);
    else turn.blocks.push({ kind: "steps", key: e.key, calls: [e.call] });
  }
  return items;
}

/** Attached files under a message: each opens the file from the workspace. */
function Files({ files }: { files: Attachment[] }) {
  if (!files.length) return null;
  return (
    <ul className="attachments" aria-label="Attached files">
      {files.map((f) => (
        <li key={f.uri}>
          <a className="attachment" href={`/api/files/raw?path=${encodeURIComponent(pathOf(f))}`} target="_blank" rel="noreferrer">
            <IconFile /><span className="name">{f.name}</span>
          </a>
        </li>
      ))}
    </ul>
  );
}

function UserMsg({ text, files, testId }: Outgoing & { testId: string }) {
  return (
    <div className="user-msg" data-testid={testId}>
      {text}
      <Files files={files} />
    </div>
  );
}

function Thread({ entries, running, queued }: { entries: Entry[]; running: boolean; queued: Outgoing[] }) {
  const items = group(entries);
  const toolBusy = running && entries.some((e) => e.kind === "tool" && (e.call.status === "pending" || e.call.status === "in_progress"));
  const streaming = running && entries[entries.length - 1]?.kind === "text"; // the reply itself shows progress
  const last = items[items.length - 1];
  const working = <div className="working" aria-label="Working">Working…</div>;
  return (
    <div className="thread">
      {items.map((it) => {
        if (it.kind === "user") return <UserMsg key={it.key} text={it.text} files={it.files} testId="user-msg" />;
        if (it.kind === "notice") return <div key={it.key} className="notice">{it.text}</div>;
        const live = running && it === last;
        return (
          <div key={it.key} className="turn">
            <Mark size={24} live={live} />
            <div className="body">
              {it.blocks.map((b) => b.kind === "text" ? (
                <div key={b.key} className="answer" data-testid="assistant-msg"><Markdown remarkPlugins={[remarkGfm]}>{b.text}</Markdown></div>
              ) : (
                <div key={b.key} className="steps" data-testid="activity">
                  {b.calls.map((c) => <Step key={c.id} call={c} running={running} />)}
                </div>
              ))}
              {live && !toolBusy && !streaming && working}
            </div>
          </div>
        );
      })}
      {running && last?.kind !== "turn" && <div className="turn"><Mark size={24} live /><div className="body">{working}</div></div>}
      {queued.map((q, i) => (
        <div key={`q${i}`} className="queued">
          <UserMsg text={q.text} files={q.files} testId="queued-msg" />
          <span className="hint">Queued · read as soon as the current step ends</span>
        </div>
      ))}
    </div>
  );
}

type Pending = { id: string; name: string; file?: Attachment; error?: string };
let pendingSeq = 0;

function Composer({ onSend, onStop, running, placeholder }: {
  onSend: (text: string, files: Attachment[]) => void; onStop?: () => void; running: boolean; placeholder?: string;
}) {
  const [text, setText] = useState("");
  const [pending, setPending] = useState<Pending[]>([]);
  const ref = useRef<HTMLTextAreaElement>(null);
  const picker = useRef<HTMLInputElement>(null);
  useEffect(() => { ref.current?.focus(); }, []);
  const uploading = pending.some((p) => !p.file && !p.error);
  const files = pending.flatMap((p) => (p.file ? [p.file] : []));
  const ready = (!!text.trim() || files.length > 0) && !uploading;

  // Attached files are saved in the workspace's uploads/ folder (never replacing a file), then sent as links.
  const attach = (list: FileList | File[]) => {
    for (const f of Array.from(list)) {
      const id = `p${pendingSeq++}`;
      setPending((p) => [...p, { id, name: f.name }]);
      uploadFile("/files", f, { folder: "uploads", keep: "true" })
        .then((r: { path: string }) => {
          const file = { name: r.path.split("/").pop() ?? f.name, uri: fileUri(r.path) };
          setPending((p) => p.map((x) => (x.id === id ? { ...x, file } : x)));
        })
        .catch((err: Error) => setPending((p) => p.map((x) => (x.id === id ? { ...x, error: err.message } : x))));
    }
  };
  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (!ready) return;
    const t = text.trim();
    setText("");
    setPending([]);
    if (ref.current) ref.current.style.height = "auto";
    onSend(t, files);
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(); }
    if (e.key === "Escape" && running && onStop) { e.preventDefault(); onStop(); }
  };
  const showStop = running && !ready && !uploading && !pending.length && onStop;
  return (
    <form className="composer" onSubmit={submit}
      onDragOver={(e) => { if (e.dataTransfer.types.includes("Files")) e.preventDefault(); }}
      onDrop={(e) => { if (e.dataTransfer.files.length) { e.preventDefault(); attach(e.dataTransfer.files); } }}>
      {pending.length > 0 && (
        <ul className="attachments" aria-label="Files to send">
          {pending.map((p) => (
            <li key={p.id} className={`attachment${p.error ? " failed" : ""}`} title={p.error}>
              {p.file || p.error ? <IconFile /> : <span className="spin" aria-label={`Uploading ${p.name}`} />}
              <span className="name">{p.file?.name ?? p.name}</span>
              {p.error && <span className="error">{p.error}</span>}
              <button type="button" className="remove" aria-label={`Remove ${p.file?.name ?? p.name}`}
                onClick={() => setPending((x) => x.filter((y) => y.id !== p.id))}><IconX /></button>
            </li>
          ))}
        </ul>
      )}
      <label htmlFor="composer" className="sr-only">Message</label>
      <textarea id="composer" ref={ref} rows={1} value={text} onKeyDown={onKey}
        placeholder={running ? "Add to the conversation…" : placeholder ?? "Ask anything"}
        onChange={(e) => { setText(e.target.value); e.target.style.height = "auto"; e.target.style.height = `${e.target.scrollHeight}px`; }} />
      <div className="bar">
        <button type="button" className="btn ghost icon attach" aria-label="Attach files" title="Attach files" onClick={() => picker.current?.click()}>
          <IconPaperclip />
        </button>
        <input ref={picker} type="file" multiple hidden data-testid="chat-upload"
          onChange={(e) => { if (e.target.files) attach(e.target.files); e.target.value = ""; }} />
        <span className="hints row-flex">
          {running ? <>Messages you send now are added without stopping · <Keys keys={["Esc"]} /> stop</>
            : <><Keys keys={["↵"]} /> send <Keys keys={["⇧", "↵"]} /> new line</>}
        </span>
        {showStop ? (
          <button className="send stop" type="button" aria-label="Stop" onClick={onStop}><span className="square" /></button>
        ) : (
          <button className="send" type="submit" aria-label="Send" disabled={!ready}><IconArrowUp /></button>
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

function Home({ onStart }: { onStart: (t: string, files?: Attachment[]) => void }) {
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
  const sid = chatId ? String(chatId) : null;
  const navigate = useNavigate();
  const location = useLocation();
  const { refresh, chats } = useApp();
  const [entries, setEntries] = useState<Entry[]>([]);
  const [running, setRunning] = useState(false);
  const [queued, setQueued] = useState<Outgoing[]>([]);
  const [error, setError] = useState("");
  const scroller = useRef<HTMLDivElement>(null);
  const current = useRef<string | null>(sid);
  current.current = sid;

  const push = (text: string) => setEntries((e) => [...e, { kind: "notice", key: nextKey(), text }]);

  const load = useCallback(async (target: string) => {
    setEntries([]);
    try {
      const r = await loadSession(target);
      if (current.current === target) setRunning(!!r?._meta?.acf?.running);
    } catch {
      if (current.current === target) navigate("/", { replace: true });
    }
  }, [navigate]);

  // Everything the agent does arrives as ACP notifications on the shared connection.
  useEffect(() => acp.on((n: AcpNotification) => {
    if (n.method === "_acf/disconnected") {
      const target = current.current;
      if (target) setTimeout(() => { if (current.current === target) load(target); }, 1000);
      return;
    }
    if (n.params.sessionId !== current.current) return;
    if (n.method === "_acf/notice") push(n.params.text);
    else if (n.method === "_acf/turn_end") {
      setRunning(false);
      setQueued([]);
      if (n.params.stopReason === "cancelled") push("Stopped.");
      if (n.params.error) setError(n.params.error);
      refresh();
    } else if (n.method === "session/update") {
      const u = n.params.update;
      if (u.sessionUpdate === "session_info_update") { refresh(); return; }
      if (u.sessionUpdate === "user_message_chunk") {
        // A queued message was read: its first chunk is its text, or its first file when it has no text.
        const content = (u as { content: unknown }).content;
        const text = textOf(content);
        const file = fileOf(content);
        setQueued((q) => {
          const i = q.findIndex((m) => (m.text ? m.text === text : !!file && m.files[0]?.uri === file.uri));
          return i < 0 ? q : [...q.slice(0, i), ...q.slice(i + 1)];
        });
      }
      setEntries((e) => reduce(e, u));
    }
  }), [load, refresh]);

  const send = async (content: string, target: string, files: Attachment[] = []) => {
    setError("");
    if (running) setQueued((q) => [...q, { text: content, files }]);
    else {
      setRunning(true);
      setEntries((e) => [...e, { kind: "user", key: nextKey(), text: content, files }]);
    }
    try {
      await prompt(target, content, files);
    } catch (err) {
      if (current.current === target && (err as Error).message !== "Connection lost") setError((err as Error).message);
    }
    if (current.current === target) { setRunning(false); setQueued([]); }
    refresh();
  };

  useEffect(() => {
    setEntries([]); setError(""); setQueued([]); setRunning(false);
    if (!sid) return;
    const pending = (location.state as { pending?: Outgoing } | null)?.pending;
    if (pending && !consumed.has(location.key)) {
      consumed.add(location.key);
      navigate(location.pathname, { replace: true, state: null });
      send(pending.text, sid, pending.files);
    } else if (!pending) {
      load(sid);
    }
  }, [sid]); // eslint-disable-line

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [entries, running, queued]);

  const start = async (text: string, files: Attachment[] = []) => {
    const s = await newSession();
    refresh();
    navigate(`/c/${s.sessionId}`, { state: { pending: { text, files } } });
  };
  const stop = () => { if (sid) cancel(sid); };
  const [confirming, setConfirming] = useState(false);
  const remove = async () => {
    if (!chatId) return;
    if (!confirming) { setConfirming(true); setTimeout(() => setConfirming(false), 4000); return; }
    await api.del(`/chats/${chatId}`);
    refresh();
    navigate("/");
  };

  if (!sid) return <Home onStart={start} />;
  const summary: ChatSummary | undefined = chats.find((c) => c.id === chatId);
  const first = entries.find((e) => e.kind === "user");
  const firstUser = (first?.text || first?.files[0]?.name || "").split("\n")[0].slice(0, 60);
  const title = summary?.title && summary.title !== "New chat" ? summary.title : firstUser;

  return (
    <>
      <Topbar crumb="Chats" title={title}>
        {running && <span className="badge success">Working</span>}
        <button className={`btn ${confirming ? "danger" : "ghost"} ${confirming ? "sm" : "icon"}`} aria-label={confirming ? "Confirm delete" : "Delete chat"}
          title="Delete chat" onClick={remove}>{confirming ? "Delete chat?" : <IconTrash />}</button>
      </Topbar>
      <div className="chat-scroll" ref={scroller}>
        <Thread entries={entries} running={running} queued={queued} />
        {error && <div className="thread" style={{ marginTop: 16 }}><div className="banner" role="alert">{error}</div></div>}
      </div>
      <div className="composer-wrap">
        <Composer key={sid} onSend={(t, f) => send(t, sid, f)} onStop={stop} running={running} />
      </div>
    </>
  );
}

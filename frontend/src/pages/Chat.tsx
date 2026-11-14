import { createContext, useCallback, useContext, useEffect, useRef, useState, type ComponentProps, type FormEvent, type KeyboardEvent } from "react";
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { acp, cancel, loadSession, newSession, prompt, setConfigOption, WORKSPACE_URI, type AcpNotification, type ConfigOption, type AgentInfo, type Attachment, type ParentSession, type SessionUpdate, type ToolStatus, type Usage, type UsageMeta } from "../acp";
import { api, formatSize, rawUrl, uploadFile, type Artifact, type ChatSummary, type Skill } from "../api";
import { Topbar, useApp } from "../App";
import { MoreMenu } from "../components/Menu";
import ChatView from "../openui/ChatView";
import { IconArrowUp, IconChat, IconCheck, IconDownload, IconFile, IconImage, IconPanel, IconPaperclip, IconTrash, IconX, Gauge, Keys, Mark, Wave } from "../components/icons";

// Navigation keys whose pending message was already sent (guards against double effects).
const consumed = new Set<string>();

/** Suggestions on the empty chat; each says which part of the agent it shows off. */
const TRY: { kind: string; text: string; prompt: string }[] = [
  { kind: "Uses your files", text: "Summarise the spreadsheets in my files", prompt: "Look at the files in my workspace and summarise any spreadsheets you find." },
  { kind: "Becomes a task", text: "Every weekday at 8:00, plan my day", prompt: "Help me set up a task that writes my plan for the day every weekday at 8:00." },
  { kind: "Becomes a skill", text: "Learn how I write my weekly update", prompt: "Make a skill for writing my weekly status update." },
];

/** A tool call as the chat knows it from ACP tool_call / tool_call_update notifications. */
type ToolCall = {
  id: string; title: string; tool?: string; input: Record<string, unknown>; status: ToolStatus; output?: string; durationMs?: number | null;
  background?: string; // job id of a command that runs in the background
  agent?: AgentInfo; // a sub-agent: what it runs on and what it has done so far
};
const inBackground = (c: ToolCall) => !!c.background && (c.status === "pending" || c.status === "in_progress");
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
        const background = t._meta?.acf?.background ?? e.call.background;
        const agent = t._meta?.acf?.agent ?? e.call.agent;
        return { ...e, call: { ...e.call, status: t.status ?? e.call.status, title: t.title ?? e.call.title, output, durationMs, background, agent } };
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
    case "agent": return { verb: "Sub-agent", detail: a.description ?? "", mono: false };
  }
  const m = call.tool?.match(/^mcp__(.+?)__(.+)$/);
  if (m) return { verb: "Used", detail: `${m[1]} · ${m[2]}`, mono: false };
  const [verb, ...rest] = call.title.split(" ");
  return { verb, detail: rest.join(" "), mono: false };
}

const secs = (ms: number | null | undefined) => (ms == null ? "" : `${(ms / 1000).toFixed(1)}s`);
const plural = (n: number, word: string) => `${n.toLocaleString("en")} ${word}${n === 1 ? "" : "s"}`;

/** What a sub-agent did: its model, its steps so far and, once it is done, its report. */
function AgentDetails({ call, finished }: { call: ToolCall; finished: boolean }) {
  const a = call.agent;
  const facts = a ? [a.model, plural(a.steps.length, "step"), ...(a.tokens ? [plural(a.tokens, "token")] : [])] : [];
  return (
    <div className="step-agent" role="group" aria-label={call.title}>
      {a && (
        <div className="meta">
          <span>{facts.join(" · ")}</span>
          {a.session && <Link to={`/c/${a.session}`} aria-label={`Open session: ${call.title}`}>Open session</Link>}
        </div>
      )}
      {a && a.steps.length > 0 && (
        <ol>
          {a.steps.map((s, i) => (
            <li key={i} className={s.ok === false ? "fail" : s.ok == null && !finished ? "live" : ""}>{s.title}</li>
          ))}
        </ol>
      )}
      {finished && <pre className="step-output">{call.output}</pre>}
    </div>
  );
}

function Step({ call, running }: { call: ToolCall; running: boolean }) {
  const [open, setOpen] = useState(false);
  const d = describe(call);
  const finished = call.status === "completed" || call.status === "failed";
  const bg = inBackground(call);
  const busy = bg || (!finished && running);
  const failed = call.status === "failed" || (!finished && !busy);
  const isAgent = call.tool === "agent";
  // A sub-agent can be opened while it works, to watch its steps; its row shows the latest one.
  const doing = isAgent && busy && !finished ? call.agent?.steps.filter((s) => s.ok == null).pop()?.title : undefined;
  const note = isAgent && call.agent ? [call.agent.model, secs(call.durationMs)].filter(Boolean).join(" · ") : secs(call.durationMs);
  return (
    <>
      <button className={`step${busy && !finished ? " live" : ""}`} onClick={() => (finished || isAgent) && setOpen(!open)} aria-expanded={open} data-testid="tool-step">
        <span className={`state${finished ? (failed ? " fail" : " ok") : busy ? " live" : " fail"}`}>
          {finished ? (failed ? <IconX /> : <IconCheck />) : busy ? <Wave label={bg ? "Running in background" : "Working"} /> : <IconX />}
        </span>
        <span className="verb">{d.verb}</span>{" "}
        <span className={`detail${d.mono ? "" : " name"}`}>{d.detail}</span>
        {doing && <span className="doing">{doing}</span>}
        {" "}<span className="time">{finished ? note : bg ? "In background" : isAgent ? call.agent?.model ?? "" : ""}</span>
      </button>
      {open && isAgent && <AgentDetails call={call} finished={finished} />}
      {open && finished && !isAgent && <pre className="step-output">{call.output}</pre>}
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

/** What an ```openui block in a reply needs: whether the reply is still streaming, and how to send a message. */
const ViewContext = createContext<{ live: boolean; onPrompt: (text: string) => void }>({ live: false, onPrompt: () => {} });
type HastNode = { type?: string; tagName?: string; value?: string; properties?: { className?: unknown }; children?: HastNode[] };
const textOfNode = (n: HastNode): string => n.value ?? (n.children ?? []).map(textOfNode).join("");

/** A code block; an ```openui block becomes a live view built from the OpenUI component library. */
function Pre({ node, children, ...rest }: ComponentProps<"pre"> & { node?: HastNode }) {
  const { live, onPrompt } = useContext(ViewContext);
  const code = node?.children?.find((c) => c.tagName === "code");
  const cls = code?.properties?.className;
  if (code && Array.isArray(cls) && cls.some((c) => c === "language-openui" || c === "language-openui-lang")) {
    return <ChatView source={textOfNode(code)} streaming={live} onPrompt={onPrompt} />;
  }
  return <pre {...rest}>{children}</pre>;
}
const MD_COMPONENTS: Components = { pre: Pre as Components["pre"] };

export function Thread({ entries, running, queued, onPrompt }: { entries: Entry[]; running: boolean; queued: Outgoing[]; onPrompt: (text: string) => void }) {
  const items = group(entries);
  const toolBusy = running && entries.some((e) => e.kind === "tool" && !inBackground(e.call) && (e.call.status === "pending" || e.call.status === "in_progress"));
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
                <ViewContext.Provider key={b.key} value={{ live, onPrompt }}>
                  <div className="answer" data-testid="assistant-msg"><Markdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>{b.text}</Markdown></div>
                </ViewContext.Provider>
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
/** The "/name" being typed just before the caret: where it starts and what was typed after the slash. */
const slashAt = (text: string, caret: number) => {
  const m = text.slice(0, caret).match(/(?:^|\s)\/([a-z0-9-]*)$/i);
  return m ? { start: caret - m[1].length - 1, query: m[1].toLowerCase() } : null;
};
const MAX_SKILL_CHOICES = 6;
let pendingSeq = 0;

/** The chat's model and, for models that have one, its effort: native selects, so they work by keyboard and on phones. */
function ModelPicker({ options, onChange }: { options: ConfigOption[]; onChange: (id: string, value: string) => void }) {
  return (
    <span className="model-picker">
      {options.map((o) => (
        <select key={o.id} className={`input picker ${o.id}`} aria-label={o.name} title={o.name} value={o.currentValue}
          onChange={(e) => onChange(o.id, e.target.value)}>
          {o.options.map((x) => <option key={x.value} value={x.value}>{x.name}</option>)}
        </select>
      ))}
    </span>
  );
}

export function Composer({ onSend, onStop, running, background = false, placeholder, initial = "", options, onOption }: {
  onSend: (text: string, files: Attachment[]) => void; onStop?: () => void; running: boolean; background?: boolean; placeholder?: string;
  initial?: string; options?: ConfigOption[]; onOption?: (id: string, value: string) => void;
}) {
  const [text, setText] = useState(initial);
  const [pending, setPending] = useState<Pending[]>([]);
  const ref = useRef<HTMLTextAreaElement>(null);
  const picker = useRef<HTMLInputElement>(null);
  useEffect(() => { ref.current?.focus(); }, []);
  // Typing "/" offers the skills; picking one puts "/name" in the message, which calls that skill.
  const [skills, setSkills] = useState<Skill[] | null>(null);
  const [slash, setSlash] = useState<{ start: number; query: string } | null>(null);
  const [choice, setChoice] = useState(0);
  const choices = slash && skills
    ? [...skills.filter((s) => s.name.startsWith(slash.query)), ...skills.filter((s) => !s.name.startsWith(slash.query) && s.name.includes(slash.query))].slice(0, MAX_SKILL_CHOICES)
    : [];
  const track = (value: string, caret: number) => {
    const at = slashAt(value, caret);
    if (at?.start !== slash?.start || at?.query !== slash?.query) setChoice(0);
    setSlash(at);
    if (at && !skills) api.get<Skill[]>("/skills").then(setSkills).catch(() => setSkills([]));
  };
  const pick = (s: Skill) => {
    if (!slash) return;
    const el = ref.current;
    const end = el?.selectionStart ?? text.length;
    const next = `${text.slice(0, slash.start)}/${s.name} ${text.slice(end).replace(/^ /, "")}`;
    setText(next);
    setSlash(null);
    const caret = slash.start + s.name.length + 2;
    requestAnimationFrame(() => { el?.focus(); el?.setSelectionRange(caret, caret); });
  };
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
    setSlash(null);
    setPending([]);
    if (ref.current) ref.current.style.height = "auto";
    onSend(t, files);
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (choices.length) {
      const move = e.key === "ArrowDown" ? 1 : e.key === "ArrowUp" ? -1 : 0;
      if (move) { e.preventDefault(); setChoice((c) => (c + move + choices.length) % choices.length); return; }
      if ((e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) || e.key === "Tab") { e.preventDefault(); pick(choices[choice]); return; }
      if (e.key === "Escape") { e.preventDefault(); setSlash(null); return; }
    }
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(); }
    if (e.key === "Escape" && (running || background) && onStop) { e.preventDefault(); onStop(); }
  };
  const showStop = (running || background) && !text.trim() && !pending.length && onStop;
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
      {choices.length > 0 && (
        <ul className="skill-menu" role="listbox" id="skill-menu" aria-label="Skills">
          {choices.map((s, i) => (
            <li key={s.name} id={`skill-${s.name}`} role="option" aria-selected={i === choice}
              onMouseDown={(e) => { e.preventDefault(); pick(s); }} onMouseMove={() => { if (i !== choice) setChoice(i); }}>
              <span className="name">/{s.name}</span>
              <span className="about">{s.description}</span>
            </li>
          ))}
        </ul>
      )}
      <label htmlFor="composer" className="sr-only">Message</label>
      <textarea id="composer" ref={ref} rows={1} value={text} onKeyDown={onKey}
        aria-autocomplete="list" aria-controls={choices.length ? "skill-menu" : undefined}
        aria-activedescendant={choices.length ? `skill-${choices[choice].name}` : undefined}
        placeholder={running ? "Add to the conversation…" : placeholder ?? "Ask anything"}
        onBlur={() => setSlash(null)}
        onSelect={(e) => { if (slash) track(e.currentTarget.value, e.currentTarget.selectionStart); }}
        onChange={(e) => {
          setText(e.target.value);
          track(e.target.value, e.target.selectionStart);
          e.target.style.height = "auto"; e.target.style.height = `${e.target.scrollHeight}px`;
        }} />
      <div className="bar">
        <button type="button" className="btn ghost icon attach" aria-label="Attach files" title="Attach files" onClick={() => picker.current?.click()}>
          <IconPaperclip />
        </button>
        <input ref={picker} type="file" multiple hidden data-testid="chat-upload"
          onChange={(e) => { if (e.target.files) attach(e.target.files); e.target.value = ""; }} />
        {options && onOption && <ModelPicker options={options} onChange={onOption} />}
        <span className="hints row-flex">
          {running ? <>Messages you send now are added without stopping · <Keys keys={["Esc"]} /> stop</>
            : background ? <>Commands are running in the background · <Keys keys={["Esc"]} /> stop them</>
            : <><Keys keys={["↵"]} /> send <Keys keys={["⇧", "↵"]} /> new line <Keys keys={["/"]} /> skills</>}
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

const IMAGE = /\.(png|jpe?g|gif|webp|svg)$/i;
const PANEL_KEY = "acf.artifacts";
const panelPref = () => { try { return localStorage.getItem(PANEL_KEY) === "open"; } catch { return false; } };

function ArtifactList({ label, items }: { label: string; items: Artifact[] }) {
  if (!items.length) return null;
  return (
    <section className="artifact-group">
      <h3>{label}</h3>
      <ul aria-label={`${label} files`}>
        {items.map((a) => {
          const dir = a.path.includes("/") ? a.path.slice(0, a.path.lastIndexOf("/")) : "";
          return (
            <li key={a.path} className="artifact">
              <a className="open" href={rawUrl(a.path)} target="_blank" rel="noreferrer" title={a.path}>
                {IMAGE.test(a.name) ? <IconImage /> : <IconFile />}
                <span className="text">
                  <span className="name">{a.name}</span>
                  <span className="meta">{dir ? `${dir} · ` : ""}{formatSize(a.size)}</span>
                </span>
              </a>
              <a className="btn ghost icon" href={rawUrl(a.path, true)} aria-label={`Download ${a.name}`} title="Download"><IconDownload /></a>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/** Files attached to this chat and files the agent made in it. They live in the workspace (see Files). */
function ArtifactsPanel({ items, onClose }: { items: Artifact[] | null; onClose: () => void }) {
  return (
    <>
      <div className="scrim artifacts-scrim" onClick={onClose} />
      <aside className="artifacts" id="artifacts" aria-label="Artifacts">
        <div className="artifacts-head">
          <h2>Artifacts</h2>
          <button className="btn ghost icon" aria-label="Close artifacts" onClick={onClose}><IconX /></button>
        </div>
        {items && !items.length && <p className="empty">Files you attach and files the agent makes in this chat show up here.</p>}
        {items && <>
          <ArtifactList label="Produced" items={items.filter((a) => a.kind === "produced")} />
          <ArtifactList label="Uploaded" items={items.filter((a) => a.kind === "uploaded")} />
        </>}
      </aside>
    </>
  );
}

const tokens = (n: number) => n.toLocaleString("en-US");
const share = (p: number) => `${p < 10 ? p.toFixed(1).replace(/\.0$/, "") : Math.round(p)}%`;
const MAX_ITEMS = 12;

/** How full the model's context window is, and what fills it: system prompt, tools, skills, messages. */
function ContextMeter({ usage }: { usage: Usage }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: globalThis.KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    const onDown = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => { document.removeEventListener("keydown", onKey); document.removeEventListener("mousedown", onDown); };
  }, [open]);
  const pct = share(usage.percent);
  const level = usage.percent >= 80 ? " high" : "";
  const estimated = usage.parts.reduce((n, p) => n + p.tokens, 0) || 1;
  return (
    <div className="context" ref={box}>
      <button className={`btn ghost sm context-toggle${open ? " on" : ""}${level}`} aria-expanded={open} aria-controls="context-usage"
        aria-label={`Context usage: ${pct} of the context window`} title="Context usage" onClick={() => setOpen(!open)}>
        <Gauge percent={usage.percent} /><span className="count">{pct}</span>
      </button>
      {open && (
        <div className="context-pop" id="context-usage" role="dialog" aria-label="Context usage">
          <div className="context-total">
            <strong>{pct}</strong>
            <span>{tokens(usage.used)} of {tokens(usage.size)} tokens</span>
          </div>
          <div className={`meter${level}`} aria-hidden="true"><span style={{ width: `${Math.min(100, usage.percent)}%` }} /></div>
          <ul className="context-parts" aria-label="What is in the context">
            {usage.parts.map((p) => (
              <li key={p.name}>
                <div className="row-flex">
                  <span className="name">{p.name}</span>
                  <span className="tokens">≈ {tokens(p.tokens)}</span>
                </div>
                <div className="meter sm" aria-hidden="true"><span style={{ width: `${(100 * p.tokens) / estimated}%` }} /></div>
                {p.count != null && <div className="items">{p.count} message{p.count === 1 ? "" : "s"}</div>}
                {p.items && (
                  <div className="items">
                    {p.items.length ? p.items.slice(0, MAX_ITEMS).join(" · ") : "None"}
                    {p.items.length > MAX_ITEMS && ` and ${p.items.length - MAX_ITEMS} more`}
                  </div>
                )}
              </li>
            ))}
          </ul>
          <p className="hint">
            {usage.measured ? "Total counted by the model provider after the latest reply; parts are estimates." : "Estimated at about 4 characters a token."}
            {" "}Older messages are summarised when the chat gets long.
          </p>
        </div>
      )}
    </div>
  );
}

function greeting(name: string) {
  const h = new Date().getHours();
  const part = h < 5 ? "Good evening" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  return `${part}, ${name}.`;
}

type Choice = Record<string, string>;
const choiceOf = (options: ConfigOption[]): Choice => Object.fromEntries(options.map((o) => [o.id, o.currentValue]));

function Home({ onStart, draft = "" }: { onStart: (t: string, files: Attachment[], choice: Choice) => void; draft?: string }) {
  const { user, counts } = useApp();
  // The model and effort the new chat will start on (the user's defaults until they pick others). The choice
  // is kept here as it is made, so a second pick before the options come back builds on the first.
  const [options, setOptions] = useState<ConfigOption[] | undefined>();
  const choice = useRef<Choice>({});
  const fetchOptions = () => {
    const asked = choice.current;
    api.get<{ configOptions: ConfigOption[] }>(`/models?${new URLSearchParams(asked)}`)
      .then((r) => { if (choice.current === asked) { setOptions(r.configOptions); choice.current = choiceOf(r.configOptions); } })
      .catch(() => {});
  };
  useEffect(() => { fetchOptions(); }, []); // eslint-disable-line
  const pick = (id: string, value: string) => {
    const next = { ...choice.current, [id]: value };
    if (id === "model") delete next.effort; // another model: its own efforts
    choice.current = next;
    setOptions((o) => o?.map((x) => (x.id in next ? { ...x, currentValue: next[x.id] } : x)));
    fetchOptions();
  };
  const n = (x: number, one: string) => `${x} ${one}${x === 1 ? "" : "s"}`;
  return (
    <>
      <Topbar title="New chat" phoneOnly />
      <div className="home">
        <div className="hello">
          <div className="hero" aria-hidden="true"><Mark size={40} /></div>
          <h1>{greeting(user.name || "there")}</h1>
          <p className="sub">What should your agent work on?</p>
        </div>
        <div className="stack">
          <Composer key={draft} initial={draft} onSend={(t, f) => onStart(t, f, choice.current)} running={false}
            placeholder="Ask anything, or describe a job to do" options={options} onOption={pick} />
          {/* What the agent has to work with; each part links to where it lives. */}
          <nav className="capabilities" aria-label="What your agent has" data-testid="status-line">
            <span className="row-flex"><span className="live-dot" aria-hidden="true" />Private computer</span>
            <span className="sep" aria-hidden="true">·</span><Link to="/files">{n(counts.files, "file")}</Link>
            <span className="sep" aria-hidden="true">·</span><Link to="/skills">{n(counts.skills, "skill")}</Link>
            <span className="sep" aria-hidden="true">·</span>
            {counts.connections
              ? <Link to="/connections">{n(counts.connections, "connected app")}</Link>
              : <Link to="/connections" className="cta">Connect an app</Link>}
          </nav>
        </div>
        <section className="try" aria-labelledby="try-label">
          <h2 className="subhead" id="try-label">Try one of these</h2>
          <div className="list">
            {TRY.map((t) => (
              <button key={t.text} className="try-row" onClick={() => onStart(t.prompt, [], choice.current)}>
                <span className="text">{t.text}</span><span className="kind">{t.kind}</span>
              </button>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}

type Loaded = Awaited<ReturnType<typeof loadSession>>;
/** What a page using a session hears about besides the thread itself. */
export type SessionEvents = {
  onLoaded?: (r: Loaded) => void;
  onLoadFailed?: () => void;
  /** A run ended (or a prompt this page sent came back). */
  onTurnEnd?: (target: string) => void;
  /** A tool call finished: files may have changed. */
  onToolDone?: (target: string) => void;
  onUsage?: (u: Usage) => void;
};

/**
 * One chat session over ACP: its thread, whether the agent runs, messages queued while it does, and how to
 * send. The chat page and an app's chat panel both use it. `sid` is the session the page shows; nothing is
 * loaded until the page calls `load` (or `send`, for a message that starts the session).
 */
export function useSession(sid: string | null, events: SessionEvents = {}) {
  const { refresh } = useApp();
  const [entries, setEntries] = useState<Entry[]>([]);
  const [running, setRunning] = useState(false);
  const [queued, setQueued] = useState<Outgoing[]>([]);
  const [error, setError] = useState("");
  const current = useRef<string | null>(sid);
  current.current = sid;
  const on = useRef(events);
  on.current = events;

  const push = (text: string) => setEntries((e) => [...e, { kind: "notice", key: nextKey(), text }]);
  const reset = useCallback(() => { setEntries([]); setError(""); setQueued([]); setRunning(false); }, []);

  const load = useCallback(async (target: string) => {
    setEntries([]);
    try {
      const r = await loadSession(target);
      if (current.current !== target) return;
      setRunning(!!r?._meta?.acf?.running);
      on.current.onLoaded?.(r);
    } catch {
      if (current.current === target) on.current.onLoadFailed?.();
    }
  }, []);

  // Everything the agent does arrives as ACP notifications on the shared connection.
  useEffect(() => acp.on((n: AcpNotification) => {
    if (n.method === "_acf/disconnected") {
      const target = current.current;
      if (target) setTimeout(() => { if (current.current === target) load(target); }, 1000);
      return;
    }
    if (n.params.sessionId !== current.current) return;
    if (n.method === "_acf/notice") push(n.params.text);
    else if (n.method === "_acf/turn_start") setRunning(true); // a background command finished and woke the agent
    else if (n.method === "_acf/turn_end") {
      setRunning(false);
      setQueued([]);
      if (n.params.stopReason === "cancelled") push("Stopped.");
      if (n.params.error) setError(n.params.error);
      on.current.onTurnEnd?.(n.params.sessionId);
      refresh();
    } else if (n.method === "session/update") {
      const u = n.params.update;
      if (u.sessionUpdate === "session_info_update") { refresh(); return; }
      if (u.sessionUpdate === "usage_update") {
        const v = u as { used: number; size: number; _meta?: { acf?: UsageMeta } };
        const meta = v._meta?.acf;
        on.current.onUsage?.({ used: v.used, size: v.size, percent: meta?.percent ?? (v.size ? (100 * v.used) / v.size : 0), measured: !!meta?.measured, parts: meta?.parts ?? [] });
        return;
      }
      if (u.sessionUpdate === "tool_call_update" && (u as { status?: ToolStatus }).status === "completed") on.current.onToolDone?.(n.params.sessionId);
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
    current.current = target; // a session made for this message, before the page shows it
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
    on.current.onTurnEnd?.(target);
    refresh();
  };
  const stop = () => { if (current.current) cancel(current.current); };
  const background = entries.some((e) => e.kind === "tool" && inBackground(e.call));
  return { entries, running, queued, error, setError, load, reset, send, stop, background };
}

export default function ChatPage() {
  const { id } = useParams();
  const chatId = id ? Number(id) : null;
  const sid = chatId ? String(chatId) : null;
  const navigate = useNavigate();
  const location = useLocation();
  const { refresh, chats, projects } = useApp();
  const [artifacts, setArtifacts] = useState<Artifact[] | null>(null);
  const [panel, setPanel] = useState(panelPref);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [options, setOptions] = useState<ConfigOption[] | undefined>();
  // A sub-agent's session: read-only, with the chat it belongs to and what the sub-agent was for.
  const [sub, setSub] = useState<{ title: string; parent: ParentSession } | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const current = useRef<string | null>(sid);
  current.current = sid;

  const loadArtifacts = useCallback(async (target: string) => {
    try {
      const r = await api.get<Artifact[]>(`/chats/${target}/artifacts`);
      if (current.current === target) setArtifacts(r);
    } catch { /* the chat is gone or not loaded yet */ }
  }, []);
  const togglePanel = () => setPanel((v) => {
    try { localStorage.setItem(PANEL_KEY, v ? "closed" : "open"); } catch { /* storage blocked */ }
    return !v;
  });

  const { entries, running, queued, error, setError, load, reset, send, stop, background } = useSession(sid, {
    onLoaded: (r) => {
      const meta = r?._meta?.acf;
      setOptions(r?.configOptions);
      setSub(meta?.parent ? { title: meta.title ?? "Sub-agent", parent: meta.parent } : null);
    },
    onLoadFailed: () => navigate("/", { replace: true }),
    onTurnEnd: loadArtifacts,
    onToolDone: loadArtifacts,
    onUsage: setUsage,
  });

  useEffect(() => {
    reset(); setArtifacts(null); setUsage(null); setSub(null);
    setOptions((location.state as { options?: ConfigOption[] } | null)?.options);
    if (!sid) return;
    loadArtifacts(sid);
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

  const start = async (text: string, files: Attachment[], choice: Choice) => {
    const s = await newSession();
    let options = s.configOptions ?? [];
    // The model first: changing it can change which efforts there are.
    for (const id of ["model", "effort"]) {
      const now = options.find((o) => o.id === id);
      if (now && choice[id] && choice[id] !== now.currentValue && now.options.some((x) => x.value === choice[id])) {
        options = (await setConfigOption(s.sessionId, id, choice[id])).configOptions;
      }
    }
    refresh();
    navigate(`/c/${s.sessionId}`, { state: { pending: { text, files }, options } });
  };
  const chooseOption = async (id: string, value: string) => {
    if (!sid) return;
    try {
      setOptions((await setConfigOption(sid, id, value)).configOptions);
    } catch (err) {
      setError((err as Error).message);
    }
  };
  const remove = async () => {
    if (!chatId) return;
    await api.del(`/chats/${chatId}`);
    refresh();
    navigate("/");
  };

  if (!sid) return <Home key={location.key} onStart={start} draft={(location.state as { draft?: string } | null)?.draft} />;
  const summary: ChatSummary | undefined = chats.find((c) => c.id === chatId);
  const first = entries.find((e) => e.kind === "user");
  const firstUser = (first?.text || first?.files[0]?.name || "").split("\n")[0].slice(0, 60);
  const title = summary?.title && summary.title !== "New chat" ? summary.title : firstUser;
  const project = sub ? undefined : projects.find((p) => p.id === summary?.project_id);

  return (
    <>
      <Topbar crumb={sub ? sub.parent.title || "Chat" : project?.name ?? "Chats"} crumbTo={project && `/projects/${project.id}`} title={sub ? sub.title : title}>
        {sub && <span className="badge plain">Sub-agent</span>}
        {running && <span className="badge live"><span className="live-dot" />Working</span>}
        {usage && <ContextMeter usage={usage} />}
        <button className={`btn ghost sm artifacts-toggle${panel ? " on" : ""}`} aria-label="Artifacts" aria-expanded={panel} aria-controls="artifacts"
          title={panel ? "Hide artifacts" : "Show artifacts"} onClick={togglePanel}>
          <IconPanel />{artifacts?.length ? <span className="count">{artifacts.length}</span> : null}
        </button>
        <MoreMenu label="Chat actions" items={[
          { label: panel ? "Hide artifacts" : "Show artifacts", icon: <IconPanel />, phoneOnly: true, onSelect: togglePanel },
          sub
            ? { label: "Back to the chat", icon: <IconChat />, onSelect: () => navigate(`/c/${sub.parent.sessionId}`) }
            : { label: "Delete chat", icon: <IconTrash />, confirm: "Yes, delete this chat", onSelect: remove },
        ]} />
      </Topbar>
      <div className="chat-layout">
        <div className="chat-col">
          <div className="chat-scroll" ref={scroller}>
            <Thread entries={entries} running={running} queued={queued} onPrompt={(t) => { if (!sub) send(t, sid); }} />
            {error && <div className="thread" style={{ marginTop: 16 }}><div className="banner" role="alert">{error}</div></div>}
          </div>
          <div className="composer-wrap">
            {sub ? (
              <div className="read-only" role="note" aria-label="Read-only session">
                <span>A sub-agent’s session. You can read it, not write in it.</span>
                <Link className="btn sm" to={`/c/${sub.parent.sessionId}`}>Back to the chat</Link>
              </div>
            ) : (
              <Composer key={sid} onSend={(t, f) => send(t, sid, f)} onStop={stop} running={running} options={options} onOption={chooseOption}
                background={background} />
            )}
          </div>
        </div>
        {panel && <ArtifactsPanel items={artifacts} onClose={togglePanel} />}
      </div>
    </>
  );
}

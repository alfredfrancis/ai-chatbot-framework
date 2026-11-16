import { createContext, useCallback, useContext, useEffect, useRef, useState, type ComponentProps, type FormEvent, type KeyboardEvent } from "react";
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { acp, cancel, loadSession, lostConnection, newSession, prompt, setConfigOption, WORKSPACE_URI, type AcpNotification, type ConfigOption, type AgentInfo, type Attachment, type Learned, type ParentSession, type SessionUpdate, type ToolStatus, type Usage, type UsageMeta } from "../acp";
import { api, ApiError, formatSize, rawUrl, uploadFile, type Artifact, type ChatSummary, type Skill } from "../api";
import { Topbar, useApp } from "../App";
import { MoreMenu } from "../components/Menu";
import ChatView from "../openui/ChatView";
import { MARKDOWN, MarkdownDoc } from "../components/MarkdownDoc";
import { IconArrowUp, IconBack, IconChat, IconCheck, IconChevron, IconCopy, IconDownload, IconExpand, IconShrink, IconFile, IconImage, IconPanel, IconPaperclip, IconSpark, IconTrash, IconX, Gauge, Keys, Mark, Wave } from "../components/icons";

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
  | { kind: "notice"; key: string; text: string; learned?: Learned };

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
/** A command's output as people read it: the "[exit code 0]" the model gets for a success is left out. */
const shownOutput = (out?: string) => (out ?? "").replace(/\n*\[exit code 0\]\s*$/, "");

/** Display names of the models this chat can use, by model id ("claude-haiku-5-5" → "Claude Haiku 5.5"). */
const ModelNames = createContext<Record<string, string>>({});
const namesOf = (options?: ConfigOption[]): Record<string, string> =>
  Object.fromEntries((options?.find((o) => o.id === "model")?.options ?? []).map((x) => [x.value.split(":").pop() ?? x.value, x.name]));
const useModelName = () => {
  const names = useContext(ModelNames);
  return (id?: string) => (id ? names[id] ?? id : "");
};
const plural = (n: number, word: string) => `${n.toLocaleString("en")} ${word}${n === 1 ? "" : "s"}`;

/** What a sub-agent did: its model, its steps so far and, once it is done, its report. */
function AgentDetails({ call, finished }: { call: ToolCall; finished: boolean }) {
  const a = call.agent;
  const modelName = useModelName();
  const facts = a ? [modelName(a.model), plural(a.steps.length, "step"), ...(a.tokens ? [plural(a.tokens, "token")] : [])] : [];
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
      {finished && <pre className="step-output">{shownOutput(call.output)}</pre>}
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
  const modelName = useModelName();
  const note = isAgent && call.agent ? [modelName(call.agent.model), secs(call.durationMs)].filter(Boolean).join(" · ") : secs(call.durationMs);
  return (
    <>
      <button className={`step${busy && !finished ? " live" : ""}`} onClick={() => (finished || isAgent) && setOpen(!open)} aria-expanded={open} data-testid="tool-step">
        <span className={`state${finished ? (failed ? " fail" : " ok") : busy ? " live" : " fail"}`}>
          {finished ? (failed ? <IconX /> : <IconCheck />) : busy ? <Wave label={bg ? "Running in background" : "Working"} /> : <IconX />}
        </span>
        <span className="verb">{d.verb}</span>{" "}
        <span className={`detail${d.mono ? "" : " name"}`}>{d.detail}</span>
        {doing && <span className="doing">{doing}</span>}
        {" "}<span className="time">{finished ? note : bg ? "In background" : isAgent ? modelName(call.agent?.model) : ""}</span>
      </button>
      {open && isAgent && <AgentDetails call={call} finished={finished} />}
      {open && finished && !isAgent && <pre className="step-output">{shownOutput(call.output) || "No output."}</pre>}
    </>
  );
}

/** What a group of finished steps did, in words: "ran 2 commands, wrote 1 file". */
function tally(calls: ToolCall[]): string {
  const counts = new Map<string, number>();
  const add = (k: string) => counts.set(k, (counts.get(k) ?? 0) + 1);
  const apps = new Set<string>();
  for (const c of calls) {
    const d = describe(c);
    if (c.tool === "bash") add("command");
    else if (c.tool === "write") add("wrote");
    else if (c.tool === "edit") add("edited");
    else if (d.verb === "Used skill") add("skill");
    else if (c.tool === "read") add("read");
    else if (c.tool === "agent") add("agent");
    else if (d.verb === "Used") apps.add(d.detail.split(" · ")[0]);
    else add("step");
  }
  const n = (k: string) => counts.get(k) ?? 0;
  const parts = [
    n("read") && `read ${plural(n("read"), "file")}`,
    n("skill") && `used ${plural(n("skill"), "skill")}`,
    n("command") && `ran ${plural(n("command"), "command")}`,
    apps.size && `used ${[...apps].join(", ")}`,
    n("agent") && plural(n("agent"), "sub-agent"),
    n("wrote") && `wrote ${plural(n("wrote"), "file")}`,
    n("edited") && `edited ${plural(n("edited"), "file")}`,
    n("step") && plural(n("step"), "other step"),
  ].filter(Boolean) as string[];
  return parts.join(", ");
}

/**
 * A finished group of steps, folded to one line that says how it went and what was done; it opens to the steps.
 * Live steps are never folded (the work shows as it happens), nor are commands still running in the background.
 */
function StepsFold({ calls, running }: { calls: ToolCall[]; running: boolean }) {
  const [open, setOpen] = useState(false);
  const failed = calls.filter((c) => c.status === "failed").length;
  const ms = calls.reduce((t, c) => t + (c.durationMs ?? 0), 0);
  const took = ms < 1000 ? "under a second" : ms < 60_000 ? `${Math.round(ms / 1000)} s` : `${Math.round(ms / 60_000)} min`;
  return (
    <div className={`steps-fold${open ? " open" : ""}`}>
      <button className="fold-head" aria-expanded={open} onClick={() => setOpen(!open)} data-testid="steps-summary">
        <span className={`state ${failed ? "fail" : "ok"}`}>{failed ? <IconX /> : <IconCheck />}</span>
        <span className="what">{failed ? `${plural(failed, "step")} failed` : `Done in ${took}`}</span>
        <span className="tally">{tally(calls.filter((c) => c.status !== "failed"))}</span>
        <span className="toggle">{open ? "Hide steps" : "Show steps"}<IconChevron /></span>
      </button>
      {open && (
        <div className="steps" data-testid="activity">
          {calls.map((c) => <Step key={c.id} call={c} running={running} />)}
        </div>
      )}
    </div>
  );
}

/** Files the agent wrote or changed in a finished turn, each as a card to open or download. A markdown file is a
 *  document: with `onOpenDoc`, its card offers to preview it beside the chat. */
function TurnFiles({ calls, onOpenDoc }: { calls: ToolCall[]; onOpenDoc?: (path: string) => void }) {
  const paths = [...new Set(calls.filter((c) => (c.tool === "write" || c.tool === "edit") && c.status === "completed")
    .map((c) => String((c.input as { path?: unknown }).path ?? "")).filter(Boolean))];
  if (!paths.length) return null;
  return (
    <ul className="turn-files" aria-label="Files from this reply">
      {paths.map((p) => {
        const name = p.split("/").pop() ?? p;
        const dir = p.includes("/") ? p.slice(0, p.lastIndexOf("/")) : "";
        const doc = onOpenDoc && MARKDOWN.test(name);
        return (
          <li key={p} className="turn-file">
            <span className="kind" aria-hidden="true">{IMAGE.test(name) ? <IconImage /> : <IconFile />}</span>
            <span className="text">
              <span className="name">{name}</span>
              <span className="meta">{doc ? "Document · " : ""}{dir ? `In Files · ${dir}` : "In Files"}</span>
            </span>
            <a className="btn ghost icon" href={rawUrl(p, true)} aria-label={`Download ${name}`} title="Download"><IconDownload /></a>
            {doc
              ? <button className="btn" type="button" aria-label={`Preview ${name}`} onClick={() => onOpenDoc(p)}>Preview</button>
              : <a className="btn" href={rawUrl(p)} target="_blank" rel="noreferrer" aria-label={`Open ${name}`}>Open</a>}
          </li>
        );
      })}
    </ul>
  );
}

type Block = { kind: "text"; key: string; text: string } | { kind: "steps"; key: string; calls: ToolCall[] };
type Item = { kind: "user"; key: string; text: string; files: Attachment[] } | { kind: "notice"; key: string; text: string; learned?: Learned } | { kind: "turn"; key: string; blocks: Block[] };

/** User messages, notices, and agent turns where consecutive tool calls share one steps card. */
function group(entries: Entry[]): Item[] {
  const items: Item[] = [];
  for (const e of entries) {
    if (e.kind === "user") { items.push({ kind: "user", key: e.key, text: e.text, files: e.files }); continue; }
    if (e.kind === "notice") { items.push({ kind: "notice", key: e.key, text: e.text, learned: e.learned }); continue; }
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

/** A change a review made, in words: "Made a new skill: greet", "Updated what I remember about you". */
const learnedLine = (c: Learned["changes"][number]) => {
  if (c.name === "memory.md") return "Updated what I remember about you";
  const skill = c.name.startsWith("skills/") ? c.name.slice(7) : c.name;
  return c.added ? `Made a new skill: ${skill}` : `Updated the skill: ${skill}`;
};

/** What the agent learned from this chat in the background, with a way to look at it and to take it back. */
function LearnedNote({ chatId, learned }: { chatId: string | null; learned: Learned }) {
  const [state, setState] = useState(learned);
  const [error, setError] = useState("");
  useEffect(() => setState(learned), [learned]);
  const undo = async () => {
    setError("");
    try {
      const m = await api.post<{ learned: Omit<Learned, "id"> }>(`/chats/${chatId}/learned/${state.id}/undo`);
      setState({ ...state, ...m.learned });
    } catch (err) {
      setError((err as Error).message);
    }
  };
  const first = state.changes[0];
  const view = first?.name.startsWith("skills/") ? `/files?path=${encodeURIComponent(first.name)}` : "/files";
  return (
    <section className={`learned${state.undone ? " undone" : ""}`} aria-label="Learned from this chat" data-testid="learned">
      <span className="icon" aria-hidden="true"><IconSpark size={20} /></span>
      <div className="text">
        <h3>{state.undone ? "Undone: nothing from this chat is kept" : "Learned from this chat"}</h3>
        <ul>{state.changes.map((c) => <li key={c.name}>{learnedLine(c)}</li>)}</ul>
        {error && <p className="error" role="alert">{error}</p>}
      </div>
      {!state.undone && <Link className="btn ghost" to={view}>View</Link>}
      {state.can_undo && chatId && <button className="btn" onClick={undo}>Undo</button>}
    </section>
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

export function Thread({ entries, running, queued, onPrompt, chatId = null, onOpenDoc }: {
  entries: Entry[]; running: boolean; queued: Outgoing[]; onPrompt: (text: string) => void; chatId?: string | null;
  onOpenDoc?: (path: string) => void;
}) {
  const items = group(entries);
  const toolBusy = running && entries.some((e) => e.kind === "tool" && !inBackground(e.call) && (e.call.status === "pending" || e.call.status === "in_progress"));
  const streaming = running && entries[entries.length - 1]?.kind === "text"; // the reply itself shows progress
  const last = items[items.length - 1];
  const working = <div className="working" aria-label="Working">Working…</div>;
  return (
    <div className="thread">
      {items.map((it) => {
        if (it.kind === "user") return <UserMsg key={it.key} text={it.text} files={it.files} testId="user-msg" />;
        if (it.kind === "notice") return it.learned
          ? <LearnedNote key={it.key} chatId={chatId} learned={it.learned} />
          : <div key={it.key} className="notice">{it.text}</div>;
        const live = running && it === last;
        const calls = it.blocks.flatMap((b) => (b.kind === "steps" ? b.calls : []));
        return (
          <div key={it.key} className="turn">
            <Mark size={24} live={live} />
            <div className="body">
              {it.blocks.map((b) => b.kind === "text" ? (
                <ViewContext.Provider key={b.key} value={{ live, onPrompt }}>
                  <div className="answer" data-testid="assistant-msg"><Markdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>{b.text}</Markdown></div>
                </ViewContext.Provider>
              ) : !live && !b.calls.some(inBackground) ? (
                <StepsFold key={b.key} calls={b.calls} running={running} />
              ) : (
                <div key={b.key} className="steps" data-testid="activity">
                  {b.calls.map((c) => <Step key={c.id} call={c} running={running} />)}
                </div>
              ))}
              {!live && <TurnFiles calls={calls} onOpenDoc={onOpenDoc} />}
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
      {options.map((o, i) => (
        <span key={o.id} className="row-flex">
          {i > 0 && <span className="sep" aria-hidden="true">·</span>}
          <select className={`input picker ${o.id}`} aria-label={o.name} title={o.name} value={o.currentValue}
            onChange={(e) => onChange(o.id, e.target.value)}>
            {o.options.map((x) => <option key={x.value} value={x.value}>{x.name}</option>)}
          </select>
        </span>
      ))}
    </span>
  );
}

/** What the message box says about the connection. "Reconnecting" waits a second, so a blip that heals at
 *  once says nothing; "Reconnected" shows for a few seconds after it. */
type ConnectionNote = "" | "Reconnecting" | "Reconnected";
const RECONNECTING_AFTER = 1000;
const RECONNECTED_FOR = 4000;

function useConnection() {
  const [offline, setOffline] = useState(acp.link === "down");
  const [note, setNote] = useState<ConnectionNote>(acp.link === "down" ? "Reconnecting" : "");
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let shown = acp.link === "down";
    const off = acp.on((n) => {
      if (n.method !== "_acf/disconnected" && n.method !== "_acf/reconnected") return;
      clearTimeout(timer);
      setOffline(acp.link === "down");
      if (n.method === "_acf/disconnected") {
        setNote("");
        timer = setTimeout(() => { shown = true; setNote("Reconnecting"); }, RECONNECTING_AFTER);
      } else if (shown) {
        shown = false;
        setNote("Reconnected");
        timer = setTimeout(() => setNote(""), RECONNECTED_FOR);
      }
    });
    return () => { off(); clearTimeout(timer); };
  }, []);
  return { offline, note };
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
  // While the connection is down the message stays in the box; it can be sent once the connection is back.
  const { offline, note } = useConnection();
  const ready = (!!text.trim() || files.length > 0) && !uploading && !offline;

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
      <span className="sr-only" role="status">
        {note === "Reconnecting" ? "Reconnecting to your agent. Your message stays here until then." : note === "Reconnected" ? "Reconnected." : ""}
      </span>
      {note && (
        <div className="row-flex wrap hint" aria-hidden="true" data-testid="connection">
          {note === "Reconnecting"
            ? <><span className="badge warning">Reconnecting</span>Your message stays here until then.</>
            : <span className="badge success">Reconnected</span>}
        </div>
      )}
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
        placeholder={running ? "Add to the conversation…" : placeholder ?? "Ask anything. Type / to use a skill"}
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
        {/* Only while something runs: how to add to it or stop it. The idle keys are the usual ones and stay unsaid. */}
        {(running || background) && (
          <span className="hints row-flex">
            {running ? <>Messages you send now are added without stopping · <Keys keys={["Esc"]} /> stop</>
              : <>Commands are running in the background · <Keys keys={["Esc"]} /> stop them</>}
          </span>
        )}
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

const plainClick = (e: { button: number; metaKey: boolean; ctrlKey: boolean; shiftKey: boolean; altKey: boolean }) =>
  e.button === 0 && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey;

function ArtifactList({ label, items, onOpenDoc }: { label: string; items: Artifact[]; onOpenDoc: (path: string) => void }) {
  if (!items.length) return null;
  return (
    <section className="artifact-group">
      <h3>{label}</h3>
      <ul aria-label={`${label} files`}>
        {items.map((a) => {
          const dir = a.path.includes("/") ? a.path.slice(0, a.path.lastIndexOf("/")) : "";
          return (
            <li key={a.path} className="artifact">
              <a className="open" href={rawUrl(a.path)} target="_blank" rel="noreferrer" title={a.path}
                onClick={(e) => { if (MARKDOWN.test(a.name) && plainClick(e)) { e.preventDefault(); onOpenDoc(a.path); } }}>
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
function ArtifactsPanel({ items, onClose, onOpenDoc }: { items: Artifact[] | null; onClose: () => void; onOpenDoc: (path: string) => void }) {
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
          <ArtifactList label="Produced" items={items.filter((a) => a.kind === "produced")} onOpenDoc={onOpenDoc} />
          <ArtifactList label="Uploaded" items={items.filter((a) => a.kind === "uploaded")} onOpenDoc={onOpenDoc} />
        </>}
      </aside>
    </>
  );
}

type DocFile = { path: string; size: number; binary: boolean; truncated: boolean; content: string };

// The document panel's width beside the chat: `reader-width` until the reader drags its edge, kept per browser.
const READER_WIDTH = 640;
const MIN_READER = 400; // `panel-width`
const MIN_CHAT = 360; // the chat beside it never gets narrower than this
const RESIZE_STEP = 16;
const WIDTH_KEY = "acf.reader-width";
const savedWidth = () => {
  try { const n = Number(localStorage.getItem(WIDTH_KEY)); return n >= MIN_READER ? n : READER_WIDTH; } catch { return READER_WIDTH; }
};
type DocState = { status: "loading" } | { status: "gone" } | { status: "error"; message: string } | ({ status: "ready" } & DocFile);

/**
 * A markdown file from Files, rendered beside the chat. `version` changes when the agent may have changed files:
 * the document then reloads in place, keeping where the reader is. `focus` changes on every request to open it.
 */
function DocPanel({ path, version, focus, onOpen, onBack, onClose }: {
  path: string; version: number; focus: number; onOpen: (path: string) => void; onBack: () => void; onClose: () => void;
}) {
  const [doc, setDoc] = useState<DocState>({ status: "loading" });
  const [copied, setCopied] = useState(false);
  const [full, setFull] = useState(false);
  const [width, setWidth] = useState(savedWidth);
  const [max, setMax] = useState(Infinity);
  const box = useRef<HTMLElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const name = path.split("/").pop() || path;
  const dir = path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : "";
  useEffect(() => { setDoc({ status: "loading" }); setCopied(false); }, [path]);
  useEffect(() => { heading.current?.focus(); }, [path, focus]);
  useEffect(() => {
    let current = true;
    api.get<DocFile>(`/files/content?path=${encodeURIComponent(path)}`).then(
      (r) => { if (current) setDoc({ status: "ready", ...r }); },
      (err) => { if (current) setDoc(err instanceof ApiError && err.status === 404 ? { status: "gone" } : { status: "error", message: (err as Error).message }); },
    );
    return () => { current = false; };
  }, [path, version]);
  useEffect(() => {
    if (!copied) return;
    const t = setTimeout(() => setCopied(false), 2000);
    return () => clearTimeout(t);
  }, [copied]);
  const copy = async () => {
    if (doc.status !== "ready") return;
    try { await navigator.clipboard.writeText(doc.content); setCopied(true); } catch { /* clipboard blocked */ }
  };
  // How wide it may get: the chat beside it keeps MIN_CHAT. Follows the window.
  useEffect(() => {
    const layout = box.current?.parentElement;
    if (!layout) return;
    const measure = () => setMax(Math.max(MIN_READER, layout.clientWidth - MIN_CHAT));
    measure();
    const seen = new ResizeObserver(measure);
    seen.observe(layout);
    return () => seen.disconnect();
  }, []);
  const shown = Math.min(width, max);
  const clamp = (w: number) => Math.round(Math.min(max, Math.max(MIN_READER, w)));
  const keepWidth = (w: number) => {
    setWidth(w);
    try { localStorage.setItem(WIDTH_KEY, String(w)); } catch { /* storage blocked */ }
  };
  const drag = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0 || !box.current) return;
    e.preventDefault();
    const handle = e.currentTarget;
    const right = box.current.getBoundingClientRect().right;
    const grab = right - e.clientX - shown; // where in the handle the pointer took hold
    let last = shown;
    handle.setPointerCapture(e.pointerId);
    document.body.classList.add("resizing");
    const move = (ev: PointerEvent) => { last = clamp(right - ev.clientX - grab); setWidth(last); };
    const end = () => {
      handle.removeEventListener("pointermove", move);
      handle.removeEventListener("pointerup", end);
      handle.removeEventListener("pointercancel", end);
      document.body.classList.remove("resizing");
      keepWidth(last);
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", end);
    handle.addEventListener("pointercancel", end);
  };
  const resizeKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const to = { ArrowLeft: shown + RESIZE_STEP, ArrowRight: shown - RESIZE_STEP, Home: MIN_READER, End: max }[e.key];
    if (to === undefined) return;
    e.preventDefault();
    keepWidth(clamp(to));
  };
  const ready = doc.status === "ready";
  return (
    <>
      {!full && <div className="scrim doc-scrim" onClick={onClose} />}
      <aside ref={box} className={`doc-panel${full ? " full" : ""}`} id="artifacts" aria-label={`Document: ${name}`}
        style={{ "--doc-width": `${shown}px` } as React.CSSProperties}
        onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); if (full) setFull(false); else onClose(); } }}>
        {!full && (
          <div className="doc-resize" role="separator" aria-orientation="vertical" aria-label="Resize the document panel" tabIndex={0}
            aria-valuenow={shown} aria-valuemin={MIN_READER} aria-valuemax={Number.isFinite(max) ? max : undefined}
            title="Drag to resize · double-click to reset" onPointerDown={drag} onKeyDown={resizeKey}
            onDoubleClick={() => keepWidth(clamp(READER_WIDTH))} />
        )}
        <div className="doc-head">
          <button className="btn ghost icon" type="button" aria-label="Back to artifacts" title="Back to artifacts" onClick={onBack}><IconBack /></button>
          <div className="text">
            <h2 ref={heading} tabIndex={-1}>{name}</h2>
            {dir && <span className="meta">{dir}</span>}
          </div>
          {ready && !doc.binary && (
            <button className="btn ghost icon" type="button" aria-label={copied ? "Copied" : "Copy text"} title={copied ? "Copied" : "Copy text"} onClick={copy}>
              {copied ? <IconCheck /> : <IconCopy />}
            </button>
          )}
          {doc.status !== "gone" && <a className="btn ghost icon" href={rawUrl(path, true)} aria-label={`Download ${name}`} title="Download"><IconDownload /></a>}
          <button className="btn ghost icon doc-full-toggle" type="button" aria-label={full ? "Exit full screen" : "Full screen"}
            title={full ? "Exit full screen" : "Full screen"} onClick={() => setFull(!full)}>{full ? <IconShrink /> : <IconExpand />}</button>
          <button className="btn ghost icon" type="button" aria-label="Close document" title="Close" onClick={onClose}><IconX /></button>
        </div>
        <div className="doc-scroll">
          {doc.status === "loading" && (
            <div className="doc-skeleton" role="status" aria-label="Loading the document"><span /><span /><span /><span /></div>
          )}
          {doc.status === "gone" && <p className="doc-note">This file is no longer in Files.</p>}
          {doc.status === "error" && <p className="doc-note" role="alert">{doc.message}</p>}
          {ready && (doc.binary
            ? <p className="doc-note">This file can't be shown here. Download it to open it.</p>
            : !doc.content.trim()
              ? <p className="doc-note">This document is empty.</p>
              : <>
                {doc.truncated && <p className="doc-note">Showing the first 500 KB. Download the file for all of it.</p>}
                <MarkdownDoc source={doc.content} path={path} onOpen={onOpen} />
              </>)}
        </div>
      </aside>
    </>
  );
}

const tokens = (n: number) => n.toLocaleString("en-US");
const share = (p: number) => `${p < 10 ? p.toFixed(1).replace(/\.0$/, "") : Math.round(p)}%`;
const MAX_ITEMS = 12;

/** From this share of the context window on, the meter sits in the top bar; below it, the chat's menu opens it. */
const CONTEXT_SHOW_AT = 50;

/** How full the model's context window is, and what fills it: system prompt, tools, skills, messages. */
function ContextMeter({ usage, open, setOpen }: { usage: Usage; open: boolean; setOpen: (open: boolean) => void }) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: globalThis.KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    const onDown = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => { document.removeEventListener("keydown", onKey); document.removeEventListener("mousedown", onDown); };
  }, [open, setOpen]);
  const pct = share(usage.percent);
  const level = usage.percent >= 80 ? " high" : "";
  const estimated = usage.parts.reduce((n, p) => n + p.tokens, 0) || 1;
  return (
    <div className="context" ref={box}>
      {usage.percent >= CONTEXT_SHOW_AT && (
        <button className={`btn ghost sm context-toggle${open ? " on" : ""}${level}`} aria-expanded={open} aria-controls="context-usage"
          aria-label={`Context usage: ${pct} of the context window`} title="Context usage" onClick={() => setOpen(!open)}>
          <Gauge percent={usage.percent} /><span className="count">{pct}</span>
        </button>
      )}
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

function Home({ onStart, draft = "", notice }: { onStart: (t: string, files: Attachment[], choice: Choice) => void; draft?: string; notice?: string }) {
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
          {notice && <p className="notice" role="status">{notice}</p>}
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

  const push = (text: string, learned?: Learned) => setEntries((e) => [...e, { kind: "notice", key: nextKey(), text, learned }]);
  const reset = useCallback(() => { setEntries([]); setError(""); setQueued([]); setRunning(false); }, []);

  const load = useCallback(async (target: string) => {
    setEntries([]);
    try {
      const r = await loadSession(target);
      if (current.current !== target) return;
      setRunning(!!r?._meta?.acf?.running);
      on.current.onLoaded?.(r);
    } catch (err) {
      // A lost connection is not a failed load: the chat loads again once the connection is back.
      if (current.current === target && !lostConnection(err)) on.current.onLoadFailed?.();
    }
  }, []);

  // Everything the agent does arrives as ACP notifications on the shared connection.
  useEffect(() => acp.on((n: AcpNotification) => {
    if (n.method === "_acf/disconnected") {
      // Whether the agent still works is known again once the chat reloads.
      setRunning(false);
      setQueued([]);
      return;
    }
    if (n.method === "_acf/reconnected") {
      if (current.current) load(current.current); // the history again, and the live run if there is one
      return;
    }
    if (n.method === "_acf/signed_out") {
      window.location.assign("/");
      return;
    }
    if (n.params.sessionId !== current.current) return;
    if (n.method === "_acf/notice") push(n.params.text, n.params._meta?.acf?.learned);
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
      if (current.current === target && !lostConnection(err)) setError((err as Error).message);
    }
    if (current.current === target) { setRunning(false); setQueued([]); }
    on.current.onTurnEnd?.(target);
    refresh();
  };
  const stop = () => { if (current.current) cancel(current.current).catch(() => {}); };
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
  // The document open beside the chat lives in the URL (?doc=path), so a reload or Back keeps it.
  const [params, setParams] = useSearchParams();
  const doc = params.get("doc");
  const [docVersion, setDocVersion] = useState(0);
  const [docFocus, setDocFocus] = useState(0);
  const opener = useRef<HTMLElement | null>(null);
  const toggleButton = useRef<HTMLButtonElement>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [usageOpen, setUsageOpen] = useState(false);
  const [options, setOptions] = useState<ConfigOption[] | undefined>();
  // A sub-agent's session: read-only, with the chat it belongs to and what the sub-agent was for.
  const [sub, setSub] = useState<{ title: string; parent: ParentSession } | null>(null);
  // The title session/load gave (null: not loaded yet), for until the chat list has this chat.
  const [loadedTitle, setLoadedTitle] = useState<string | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const current = useRef<string | null>(sid);
  current.current = sid;

  const loadArtifacts = useCallback(async (target: string) => {
    try {
      const r = await api.get<Artifact[]>(`/chats/${target}/artifacts`);
      if (current.current === target) setArtifacts(r);
    } catch { /* the chat is gone or not loaded yet */ }
  }, []);
  const keepPanel = (open: boolean) => {
    try { localStorage.setItem(PANEL_KEY, open ? "open" : "closed"); } catch { /* storage blocked */ }
    setPanel(open);
  };
  const dropDoc = () => setParams((p) => { p.delete("doc"); return p; }, { replace: true });
  const openDoc = useCallback((path: string) => {
    const active = document.activeElement;
    // Focus goes back to what opened the document; a link inside the panel goes away with it.
    if (active instanceof HTMLElement && !active.closest(".doc-panel")) opener.current = active;
    setDocFocus((n) => n + 1);
    if (params.get("doc") !== path) setParams((p) => { p.set("doc", path); return p; });
  }, [params, setParams]);
  const closeDoc = () => {
    dropDoc();
    keepPanel(false);
    const back = opener.current?.isConnected ? opener.current : toggleButton.current;
    opener.current = null;
    requestAnimationFrame(() => back?.focus());
  };
  const shown = panel || !!doc;
  const togglePanel = () => { if (doc) dropDoc(); keepPanel(!shown); };
  const filesChanged = (target: string) => { loadArtifacts(target); setDocVersion((n) => n + 1); };

  const { entries, running, queued, error, setError, load, reset, send, stop, background } = useSession(sid, {
    onLoaded: (r) => {
      const meta = r?._meta?.acf;
      setOptions(r?.configOptions);
      setLoadedTitle(meta?.title ?? "New chat");
      setSub(meta?.parent ? { title: meta.title ?? "Sub-agent", parent: meta.parent } : null);
    },
    onLoadFailed: () => {
      refresh();
      navigate("/", { replace: true, state: { notice: "That chat could not be opened. It may have been deleted." } });
    },
    onTurnEnd: filesChanged,
    onToolDone: filesChanged,
    onUsage: setUsage,
  });

  useEffect(() => {
    reset(); setArtifacts(null); setUsage(null); setUsageOpen(false); setSub(null); setLoadedTitle(null);
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

  if (!sid) {
    const state = location.state as { draft?: string; notice?: string } | null;
    return <Home key={location.key} onStart={start} draft={state?.draft} notice={state?.notice} />;
  }
  const summary: ChatSummary | undefined = chats.find((c) => c.id === chatId);
  const first = entries.find((e) => e.kind === "user");
  const firstUser = (first?.text || first?.files[0]?.name || "").split("\n")[0].slice(0, 60);
  // A chat without a title of its own ("New chat") is named by its first message; until its title is known,
  // none (not the first message, which a titled chat such as an app's would then flash).
  const named = summary?.title ?? loadedTitle;
  const title = named === null ? "" : named && named !== "New chat" ? named : firstUser;
  const project = sub ? undefined : projects.find((p) => p.id === summary?.project_id);

  return (
    <>
      <Topbar crumb={sub ? sub.parent.title || "Chat" : project?.name ?? "Chats"} crumbTo={project && `/projects/${project.id}`} title={sub ? sub.title : title}>
        {sub && <span className="badge plain">Sub-agent</span>}
        {running && <span className="badge live"><span className="live-dot" />Working</span>}
        {usage && <ContextMeter usage={usage} open={usageOpen} setOpen={setUsageOpen} />}
        <button ref={toggleButton} className={`btn ghost sm artifacts-toggle${shown ? " on" : ""}`} aria-label="Artifacts" aria-expanded={shown} aria-controls="artifacts"
          title={shown ? "Hide artifacts" : "Show artifacts"} onClick={togglePanel}>
          <IconPanel />{artifacts?.length ? <span className="count">{artifacts.length}</span> : null}
        </button>
        <MoreMenu label="Chat actions" items={[
          { label: shown ? "Hide artifacts" : "Show artifacts", icon: <IconPanel />, phoneOnly: true, onSelect: togglePanel },
          ...(usage ? [{ label: "Context usage", icon: <Gauge percent={usage.percent} />, onSelect: () => setUsageOpen(true) }] : []),
          sub
            ? { label: "Back to the chat", icon: <IconChat />, onSelect: () => navigate(`/c/${sub.parent.sessionId}`) }
            : { label: "Delete chat", icon: <IconTrash />, confirm: "Yes, delete this chat", onSelect: remove },
        ]} />
      </Topbar>
      <div className="chat-layout">
        <div className="chat-col">
          <div className="chat-scroll" ref={scroller}>
            <ModelNames.Provider value={namesOf(options)}>
              <Thread entries={entries} running={running} queued={queued} chatId={sid} onPrompt={(t) => { if (!sub) send(t, sid); }} onOpenDoc={openDoc} />
            </ModelNames.Provider>
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
        {doc ? (
          <DocPanel path={doc} version={docVersion} focus={docFocus} onOpen={openDoc} onClose={closeDoc}
            onBack={() => { dropDoc(); keepPanel(true); }} />
        ) : panel && <ArtifactsPanel items={artifacts} onClose={togglePanel} onOpenDoc={openDoc} />}
      </div>
    </>
  );
}

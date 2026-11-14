import { Renderer, type ActionEvent, type OpenUIError, type ParseResult } from "@openuidev/react-lang";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { Attachment } from "../acp";
import { api, type AppDetail } from "../api";
import { Topbar, useApp } from "../App";
import { IconChat, IconX, Mark } from "../components/icons";
import { AppApiContext, openuiLibrary, type AppApi } from "../openui/library";
import { Composer, Thread, useSession } from "./Chat";

type Result = Record<string, unknown>;
type Session = ReturnType<typeof useSession>;

const CHAT_KEY = "acf.app-chat";
const chatPref = () => { try { return localStorage.getItem(CHAT_KEY) === "open"; } catch { return false; } };

/**
 * The app's own chat, on the right: what the user says here changes the app, and the screen follows. It is not
 * modal: where it overlays the screen (narrow windows), the rest of the screen stays bright and usable.
 */
function AppChat({ title, chatId, session, onSend, onClose }: {
  title: string; chatId: number | null; session: Session; onSend: (text: string, files: Attachment[]) => void; onClose: () => void;
}) {
  const { entries, running, queued, error, stop, background } = session;
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [entries, running, queued]);
  return (
    <aside className="app-chat" id="app-chat" aria-label={`${title} chat`}>
      <div className="app-chat-head">
        <h2>Chat</h2>
        {chatId && <Link className="btn ghost sm" to={`/c/${chatId}`} title="Open this chat on its own page">Open chat</Link>}
        <button className="btn ghost icon" aria-label="Close chat" title="Close chat" onClick={onClose}><IconX /></button>
      </div>
      <div className="app-chat-scroll" ref={scroller}>
        {entries.length === 0 && !running ? (
          <div className="app-chat-empty">
            <span className="hero" aria-hidden="true"><Mark size={32} /></span>
            <p className="title">Tell the agent what to change in {title}</p>
            <p className="hint">A new card, another column, different words. The screen updates as the agent works.</p>
          </div>
        ) : (
          <Thread entries={entries} running={running} queued={queued} onPrompt={(t) => onSend(t, [])} />
        )}
        {error && <div className="banner" role="alert">{error}</div>}
      </div>
      <div className="app-chat-composer">
        <Composer onSend={onSend} onStop={stop} running={running} background={background} placeholder={`Change ${title}…`} />
      </div>
    </aside>
  );
}

/**
 * A personal app: apps/<id>/app.oui (OpenUI Lang) rendered with the app component library. Every call it
 * makes - Query/Mutation tools, buttons, the board - goes to the app action API, scoped to the app.
 */
export default function AppPage() {
  const { id = "" } = useParams();
  const { refresh } = useApp();
  const [app, setApp] = useState<AppDetail | null>(null);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState("");
  const [problems, setProblems] = useState<string[]>([]);
  const [chatOpen, setChatOpen] = useState(chatPref);
  const toggleChat = () => setChatOpen((v) => {
    try { localStorage.setItem(CHAT_KEY, v ? "closed" : "open"); } catch { /* storage blocked */ }
    return !v;
  });

  const load = useCallback(async () => {
    try {
      setApp(await api.get<AppDetail>(`/apps/${id}`));
      setMissing(false);
    } catch {
      setMissing(true);
    }
  }, [id]);
  useEffect(() => { setApp(null); setError(""); setProblems([]); load(); }, [load]);

  // The agent edits the screen and its files in the background: follow it.
  const running = app?.running ?? false;
  const wasRunning = useRef(false);
  useEffect(() => {
    const t = setInterval(() => { if (document.visibilityState === "visible") load(); }, running ? 1000 : 4000);
    if (wasRunning.current && !running) refresh();
    wasRunning.current = running;
    return () => clearInterval(t);
  }, [load, running, refresh]);

  // The app's own chat, followed whether the panel is open or not: when one of its tool calls finishes, the
  // agent may have changed the screen or its files, so read both again (the screen keeps what was typed).
  const sid = app?.chat_id ? String(app.chat_id) : null;
  const [revision, setRevision] = useState(0);
  const queryIds = useRef<string[]>([]);
  const changed = useCallback(() => { load(); setRevision((r) => r + 1); }, [load]);
  const session = useSession(sid, { onToolDone: changed, onTurnEnd: changed });
  const made = useRef<string | null>(null); // a chat made here for a message: that message's prompt follows it
  useEffect(() => {
    if (made.current && made.current === sid) return;
    session.reset();
    if (sid) session.load(sid);
  }, [sid]); // eslint-disable-line

  const sendChat = async (text: string, files: Attachment[]) => {
    let target = sid;
    if (!target) {
      try {
        const r = await api.post<{ chat_id: number }>(`/apps/${id}/chat`);
        target = made.current = String(r.chat_id);
        setApp((a) => a && { ...a, chat_id: r.chat_id });
      } catch (e) {
        session.setError((e as Error).message);
        return;
      }
    }
    session.send(text, target, files);
  };

  /** One action; throws with the server's message (Mutations show it as their error). */
  const call = useCallback(async (action: string, args: Result): Promise<Result> => {
    const r = await api.post<Result>(`/apps/${id}/actions`, { action, args });
    if (action === "ask_agent") { setApp((a) => a && { ...a, running: true, chat_id: (r.chat_id as number) ?? a.chat_id }); refresh(); }
    return r;
  }, [id, refresh]);
  /** The same for components: a failure shows as a banner instead. */
  const act: AppApi["act"] = useCallback(async (action, args) => {
    try { setError(""); return await call(action, args); } catch (e) { setError((e as Error).message); return null; }
  }, [call]);
  const appApi: AppApi = useMemo(() => ({ act, revision, queries: () => queryIds.current }), [act, revision]);
  const onParse = useCallback((r: ParseResult | null) => { queryIds.current = r?.queryStatements.map((q) => q.statementId) ?? []; }, []);

  const tools = useMemo(() => ({
    read_file: (a: Result) => call("read_file", a),
    update_file: (a: Result) =>
      call("update_file", { ...a, content: typeof a.content === "string" ? a.content : JSON.stringify(a.content, null, 2) + "\n" }),
    ask_agent: (a: Result) => call("ask_agent", a),
    run: (a: Result) => call("run", a),
    mcp: (a: Result) => call("mcp", a),
  }), [call]);

  const onAction = useCallback((e: ActionEvent) => {
    if (e.type === "continue_conversation") {
      const context = e.params?.context;
      const prompt = e.humanFriendlyMessage + (context !== undefined ? `\n\nContext: ${JSON.stringify(context)}` : "");
      act("ask_agent", { prompt, event: "The user pressed a button." });
    } else if (e.type === "open_url") {
      const url = String(e.params?.url ?? "");
      if (/^https?:\/\//.test(url)) window.open(url, "_blank", "noopener,noreferrer");
    }
  }, [act]);

  const onError = useCallback((errors: OpenUIError[]) => {
    setProblems(errors.map((e) => [e.code, e.message].filter(Boolean).join(": ")));
  }, []);

  const askFix = () =>
    act("ask_agent", {
      prompt: `Fix apps/${id}/app.oui so it renders. Read skills/openui/SKILL.md first.\n\n${problems.join("\n")}`,
      event: "The screen has errors.",
    });

  if (missing) {
    return (
      <>
        <Topbar crumb="Apps" title={id} />
        <div className="page"><div className="page-inner"><div className="empty">This app doesn’t exist any more. Ask the agent to make it again.</div></div></div>
      </>
    );
  }
  if (!app) return <Topbar crumb="Apps" title={id} />;

  return (
    <>
      <Topbar crumb="Apps" title={app.title}>
        {app.running && <span className="app-working" role="status"><span className="live-dot" aria-hidden="true" />Agent working…</span>}
        <button className={`btn ghost sm app-chat-toggle${chatOpen ? " on" : ""}`} aria-label="App chat" aria-expanded={chatOpen}
          aria-controls="app-chat" title={chatOpen ? "Hide chat" : "Change this app in a chat"} onClick={toggleChat}>
          <IconChat /><span className="label">Chat</span>
        </button>
      </Topbar>
      <div className="chat-layout">
        <div className="page">
          <div className="page-inner wide app-page">
            <div>
              <h1>{app.title}</h1>
              {app.description && <p className="lead">{app.description}</p>}
            </div>
            {app.error && <div className="banner" role="alert">{app.error} Ask the agent to fix it.</div>}
            {error && <div className="banner" role="alert">{error}</div>}
            {problems.length > 0 && (
              <div className="banner stack" role="alert">
                <span>This screen has problems:</span>
                <ul className="oui-problems">{problems.slice(0, 5).map((p, i) => <li key={i}>{p}</li>)}</ul>
                <span><button className="btn sm" onClick={askFix}>Ask the agent to fix it</button></span>
              </div>
            )}
            <AppApiContext.Provider value={appApi}>
              <Renderer key={id} response={app.source} library={openuiLibrary} isStreaming={false}
                toolProvider={tools} onAction={onAction} onError={onError} onParseResult={onParse} />
            </AppApiContext.Provider>
          </div>
        </div>
        {chatOpen && <AppChat title={app.title} chatId={app.chat_id} session={session} onSend={sendChat} onClose={toggleChat} />}
      </div>
    </>
  );
}

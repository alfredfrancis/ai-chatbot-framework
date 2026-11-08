import { Renderer, type ActionEvent, type OpenUIError } from "@openuidev/react-lang";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type AppDetail } from "../api";
import { Topbar, useApp } from "../App";
import { AppApiContext, openuiLibrary, type AppApi } from "../openui/library";

type Result = Record<string, unknown>;

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

  /** One action; throws with the server's message (Mutations show it as their error). */
  const call = useCallback(async (action: string, args: Result): Promise<Result> => {
    const r = await api.post<Result>(`/apps/${id}/actions`, { action, args });
    if (action === "ask_agent") { setApp((a) => a && { ...a, running: true, chat_id: (r.chat_id as number) ?? a.chat_id }); refresh(); }
    return r;
  }, [id, refresh]);
  /** The same for components: a failure shows as a banner instead. */
  const appApi: AppApi = useMemo(() => ({
    act: async (action, args) => {
      try { setError(""); return await call(action, args); } catch (e) { setError((e as Error).message); return null; }
    },
  }), [call]);

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
      appApi.act("ask_agent", { prompt, event: "The user pressed a button." });
    } else if (e.type === "open_url") {
      const url = String(e.params?.url ?? "");
      if (/^https?:\/\//.test(url)) window.open(url, "_blank", "noopener,noreferrer");
    }
  }, [appApi]);

  const onError = useCallback((errors: OpenUIError[]) => {
    setProblems(errors.map((e) => [e.code, e.message].filter(Boolean).join(": ")));
  }, []);

  const askFix = () =>
    appApi.act("ask_agent", {
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
        {app.chat_id && <Link className="btn ghost sm" to={`/c/${app.chat_id}`}>Open chat</Link>}
      </Topbar>
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
              toolProvider={tools} onAction={onAction} onError={onError} />
          </AppApiContext.Provider>
        </div>
      </div>
    </>
  );
}

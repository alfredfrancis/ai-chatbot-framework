import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, effortName, type ModelEntry, type ProviderEntry, type Settings } from "../api";
import { Toggle } from "../components/Toggle";
import { PageHeader, Topbar, useApp } from "../App";

type SandboxStatus = { kind: string; state: string; name?: string; image?: string };
type AcpToken = { hint: string; created_at: string; last_used_at: string | null };
type AcpTokenState = { token: AcpToken | null; endpoint: string; value?: string };

const when = (iso: string) => new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

/** The optional access token that lets other apps use this agent over the Agent Client Protocol. */
function ExternalApps() {
  const [state, setState] = useState<AcpTokenState | null>(null);
  const [value, setValue] = useState("");
  const [copied, setCopied] = useState(false);
  useEffect(() => { api.get<AcpTokenState>("/acp/token").then(setState).catch(() => {}); }, []);
  if (!state) return null;
  const url = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}${state.endpoint}`;
  const create = async () => {
    if (state.token && !confirm("Replace the access token? Apps using the current one are disconnected.")) return;
    const r = await api.post<AcpTokenState>("/acp/token");
    setState(r);
    setValue(r.value ?? "");
    setCopied(false);
  };
  const revoke = async () => {
    if (!confirm("Turn off access for other apps? Apps using the token are disconnected.")) return;
    setState(await api.del<AcpTokenState>("/acp/token"));
    setValue("");
  };
  const copy = async () => { await navigator.clipboard?.writeText(value).catch(() => {}); setCopied(true); };
  return (
    <section className="stack" aria-labelledby="external-apps">
      <div>
        <h2 id="external-apps">External apps</h2>
        <p className="lead">Use your agent from other apps, such as code editors, that speak the Agent Client Protocol (ACP). Off until you create a token.</p>
      </div>
      <div className="card">
        <div className="field">
          <label htmlFor="acp-url">ACP address</label>
          <input id="acp-url" className="input mono" readOnly value={url} onFocus={(e) => e.target.select()} />
          <span className="hint">Apps send the token as <code>Authorization: Bearer …</code>. Apps that start an agent as a program can run <code>python -m acf.acp_bridge --url {url}</code> with the token in <code>ACF_ACP_TOKEN</code>.</span>
        </div>
        {value && (
          <div className="field">
            <label htmlFor="acp-token">New access token</label>
            <div className="row-flex">
              <input id="acp-token" className="input mono" readOnly value={value} onFocus={(e) => e.target.select()} />
              <button type="button" className="btn" onClick={copy}>{copied ? "Copied" : "Copy"}</button>
            </div>
            <span className="hint" role="status">Copy it now. It won't be shown again.</span>
          </div>
        )}
        <div className="row-flex between wrap">
          <span className="hint" data-testid="acp-token-status">
            {state.token
              ? `Token ending in ${state.token.hint} · created ${when(state.token.created_at)} · ${state.token.last_used_at ? `last used ${when(state.token.last_used_at)}` : "not used yet"}`
              : "No token. Other apps can't connect."}
          </span>
          <span className="row-flex">
            {state.token && <button type="button" className="btn danger sm" onClick={revoke}>Revoke token</button>}
            <button type="button" className={`btn${state.token ? " sm" : ""}`} onClick={create}>{state.token ? "Replace token" : "Create access token"}</button>
          </span>
        </div>
      </div>
    </section>
  );
}

const SECTIONS = [
  { id: "model-settings", label: "Models" }, { id: "providers", label: "Providers" },
  { id: "external-apps", label: "External apps" }, { id: "sandbox", label: "Computer" }, { id: "account", label: "Account" },
];
const tokens = (n: number) => (n >= 1_000_000 ? `${+(n / 1_000_000).toFixed(2)}M` : `${Math.round(n / 1000)}K`);
const trim = (u: string) => u.trim().replace(/\/+$/, "");
type Update = (r: Settings) => void;

/** Saved feedback that fades, and errors that stay. */
function useStatus() {
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const run = async (fn: () => Promise<void>, done = "Saved") => {
    setError("");
    try {
      await fn();
      setMsg(done);
      setTimeout(() => setMsg(""), 2000);
    } catch (err) {
      setError((err as Error).message);
    }
  };
  return { msg, error, run };
}

/** The model and effort new chats start on. Saved as soon as they change, like the switches below. */
function Defaults({ s, onSaved }: { s: Settings; onSaved: Update }) {
  const { msg, error, run } = useStatus();
  // What the selects show: the latest choice, so a second change before the first is saved builds on it.
  const [choice, setChoice] = useState({ model: s.model, effort: s.effort });
  const queue = useRef(Promise.resolve());
  const current = s.models.find((m) => m.key === (choice.model || s.defaults.model));
  const efforts = current?.efforts ?? [];
  const save = (model: string, effort: string) => {
    const next = s.models.find((m) => m.key === (model || s.defaults.model));
    const sent = { model, effort: next?.efforts.includes(effort) ? effort : "" };
    setChoice(sent);
    // One save at a time, in order, so an earlier one can't land last and undo a later one.
    queue.current = queue.current.then(() => run(async () => onSaved(await api.put<Settings>("/settings", sent))));
  };
  const serverDefault = s.models.find((m) => m.key === s.defaults.model)?.name ?? s.defaults.model;
  return (
    <section className="stack" id="model-settings" aria-labelledby="models-title">
      <div>
        <div className="row-flex between">
          <h2 id="models-title">Models</h2>
          <span className="hint" role="status">{msg}</span>
        </div>
        <p className="lead">New chats start on these. You can switch model and effort in any chat, next to the message box.</p>
      </div>
      <div className="card">
        <div className="grid-2">
          <div className="field">
            <label htmlFor="default-model">Default model</label>
            <select id="default-model" className="input" value={choice.model} onChange={(e) => save(e.target.value, choice.effort)}>
              <option value="">{serverDefault} (server default)</option>
              {s.models.filter((m) => m.enabled && m.key !== s.defaults.model).map((m) => <option key={m.key} value={m.key}>{m.name}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="default-effort">Default effort</label>
            <select id="default-effort" className="input" value={efforts.includes(choice.effort) ? choice.effort : ""} disabled={!efforts.length}
              onChange={(e) => save(choice.model, e.target.value)}>
              <option value="">{efforts.length ? `${effortName(current?.effort || "medium")} (model's default)` : "Not available for this model"}</option>
              {efforts.map((x) => <option key={x} value={x}>{effortName(x)}</option>)}
            </select>
            <span className="hint">More effort thinks longer: better answers to hard questions, but slower and costlier.</span>
          </div>
        </div>
        {error && <div className="banner" role="alert">{error}</div>}
      </div>
    </section>
  );
}

/** One model: on or off in the chat's model picker; its options hold the token window. */
function ModelRow({ m, s, onSaved }: { m: ModelEntry; s: Settings; onSaved: Update }) {
  const [open, setOpen] = useState(false);
  const [window, setWindow] = useState(m.window && m.window !== m.context_window ? String(m.window) : "");
  const { error, run } = useStatus();
  const isDefault = m.key === (s.model || s.defaults.model);
  const toggle = (enabled: boolean) => run(async () => onSaved(await api.patch<Settings>("/settings/models", { key: m.key, enabled })));
  const saveWindow = (e: FormEvent) => {
    e.preventDefault();
    run(async () => {
      onSaved(await api.patch<Settings>("/settings/models", { key: m.key, context_window: Number(window) || 0 }));
      setOpen(false);
    });
  };
  const remove = () => run(async () => onSaved(await api.del<Settings>(`/settings/models?key=${encodeURIComponent(m.key)}`)));
  return (
    <div className="lrow model-row" data-testid="model-row">
      <div className="grow">
        <div className="title row-flex wrap">
          {m.name}
          {isDefault && <span className="badge plain">Default</span>}
          {m.custom && <span className="badge plain">Added by you</span>}
        </div>
        {(m.name !== m.id || m.window > 0) && (
          <div className="meta">
            {m.name !== m.id && <span className="mono">{m.id}</span>}
            {m.name !== m.id && m.window > 0 && " · "}
            {m.window > 0 && `${tokens(m.window)} token window`}
          </div>
        )}
      </div>
      <div className="side">
        <button type="button" className={`btn ghost sm${open ? " on" : ""}`} aria-expanded={open} aria-label={`Options for ${m.name}`} onClick={() => setOpen(!open)}>Options</button>
        <Toggle label={`Use ${m.name}`} checked={m.enabled} onChange={toggle} />
      </div>
      {open && (
        <form className="row-panel" onSubmit={saveWindow} aria-label={`${m.name} options`}>
          <div className="field">
            <label htmlFor={`window-${m.key}`}>Token window</label>
            <input id={`window-${m.key}`} className="input mono" inputMode="numeric" value={window}
              onChange={(e) => setWindow(e.target.value.replace(/[^0-9]/g, ""))}
              placeholder={m.context_window ? String(m.context_window) : "The model's own"} />
            <span className="hint">
              How much of the conversation the model keeps in view. Older messages are summarised when a chat fills 80% of it.
              {m.max_context_window ? ` At most ${m.max_context_window.toLocaleString("en-US")} tokens.` : ""}
            </span>
          </div>
          <div className="row-flex wrap">
            <button className="btn sm" type="submit">Save token window</button>
            {m.custom && <button type="button" className="btn danger sm" disabled={isDefault} onClick={remove}>Remove model</button>}
          </div>
        </form>
      )}
      {error && <div className="banner" role="alert" style={{ flexBasis: "100%" }}>{error}</div>}
    </div>
  );
}

/** A provider: its key (the user's, or the server's), and its models. */
function Provider({ p, s, onSaved, startOpen = false }: { p: ProviderEntry; s: Settings; onSaved: Update; startOpen?: boolean }) {
  const [editing, setEditing] = useState(startOpen);
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState(p.base_url);
  const [advanced, setAdvanced] = useState(!!p.base_url);
  const [modelId, setModelId] = useState("");
  const key = useStatus();
  const add = useStatus();
  useEffect(() => setBaseUrl(p.base_url), [p.base_url]);
  const models = s.models.filter((m) => m.provider === p.id);
  // The server's key only goes to the server's own provider and address.
  const serverKey = s.defaults.has_api_key && p.id === s.defaults.provider && ["", trim(s.defaults.base_url)].includes(trim(baseUrl));
  const ready = p.has_api_key || serverKey;
  const put = (k: string | null) => api.put<Settings>(`/settings/providers/${p.id}`, { base_url: baseUrl, api_key: k });
  const saveKey = (e: FormEvent) => {
    e.preventDefault();
    key.run(async () => { onSaved(await put(apiKey || null)); setApiKey(""); setEditing(false); });
  };
  const addModel = (e: FormEvent) => {
    e.preventDefault();
    add.run(async () => { onSaved(await api.post<Settings>("/settings/models", { provider: p.id, id: modelId.trim() })); setModelId(""); });
  };
  const status = p.has_api_key ? "Your key is saved" : serverKey ? "Uses the server's key" : "Needs an API key before its models can answer";
  return (
    <section className="list provider" aria-label={p.name}>
      <div className="lrow provider-head">
        <div className="grow">
          <h3 className="title">{p.name}</h3>
          <div className="meta row-flex wrap">
            {!ready && <span className="badge warning">No API key</span>}
            <span>{status}{p.base_url ? ` · ${p.base_url}` : ""}</span>
          </div>
        </div>
        <div className="side">
          {key.msg && <span className="hint" role="status">{key.msg}</span>}
          <button type="button" className={`btn sm${editing ? " on" : ""}`} aria-expanded={editing} onClick={() => setEditing(!editing)}>
            {p.has_api_key ? "Change key" : serverKey ? "Use my own key" : "Add key"}
          </button>
        </div>
        {editing && (
          <form className="row-panel" onSubmit={saveKey} aria-label={`${p.name} key`}>
            <div className="field">
              <label htmlFor={`key-${p.id}`}>{p.name} API key</label>
              <input id={`key-${p.id}`} className="input" type="password" autoComplete="off" value={apiKey} onChange={(e) => setApiKey(e.target.value)}
                placeholder={p.has_api_key ? "•••••••• (saved)" : serverKey ? "Using the server's key" : "Paste your API key"} />
              <span className="hint">
                {!p.has_api_key && !serverKey && s.defaults.has_api_key && p.id === s.defaults.provider
                  ? "The server's key only works with its own model provider and address. Add your own key for this one."
                  : "Stored encrypted, and only ever sent to this provider."}
              </span>
            </div>
            {advanced || p.id === "openai" ? (
              <div className="field">
                <label htmlFor={`url-${p.id}`}>{p.name} server address <span className="hint">(optional)</span></label>
                <input id={`url-${p.id}`} className="input mono" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder={p.id === "openai" ? "http://localhost:11434/v1" : "https://…"} />
                <span className="hint">{p.id === "openai" ? "For any OpenAI-compatible server: Ollama, OpenRouter, vLLM, LiteLLM. " : ""}Leave empty for the provider's own.</span>
              </div>
            ) : (
              <button type="button" className="btn ghost sm" style={{ alignSelf: "flex-start" }} onClick={() => setAdvanced(true)}>Use a custom server address</button>
            )}
            {key.error && <div className="banner" role="alert">{key.error}</div>}
            <div className="row-flex wrap">
              <button className="btn sm" type="submit" disabled={!apiKey && baseUrl === p.base_url}>Save {p.name} key</button>
              <button type="button" className="btn ghost sm" onClick={() => { setEditing(false); setApiKey(""); setBaseUrl(p.base_url); }}>Cancel</button>
              {p.has_api_key && <button type="button" className="btn danger sm" onClick={() => key.run(async () => onSaved(await put("")), "Key removed")}>Remove saved key</button>}
            </div>
          </form>
        )}
      </div>
      {models.map((m) => <ModelRow key={m.key} m={m} s={s} onSaved={onSaved} />)}
      {s.custom_models && (
        <form className="lrow add-model" onSubmit={addModel} aria-label={`Add a model to ${p.name}`}>
          <label className="sr-only" htmlFor={`new-${p.id}`}>New {p.name} model id</label>
          <input id={`new-${p.id}`} className="input mono" placeholder={p.id === "openai" ? "Another model id, e.g. llama3.1:8b" : "Another model id"}
            value={modelId} onChange={(e) => setModelId(e.target.value)} />
          <button className="btn sm" type="submit" disabled={!modelId.trim()}>Add model</button>
          {add.error && <div className="banner" role="alert" style={{ flexBasis: "100%" }}>{add.error}</div>}
        </form>
      )}
    </section>
  );
}

function Providers({ s, onSaved }: { s: Settings; onSaved: Update }) {
  const [extra, setExtra] = useState<string[]>([]);
  const listed = [...s.providers, ...extra.filter((x) => !s.providers.some((p) => p.id === x))
    .map((x) => ({ id: x, name: x, base_url: "", has_api_key: false, server: false }))];
  const more = s.allowed_providers.filter((x) => x !== "*" && !listed.some((p) => p.id === x));
  return (
    <section className="stack" id="providers" aria-labelledby="providers-title">
      <div>
        <h2 id="providers-title">Providers</h2>
        <p className="lead">Switch on the models you want to pick from in chats. A provider's models answer once it has an API key.</p>
      </div>
      {listed.map((p) => <Provider key={p.id} p={p} s={s} onSaved={onSaved} startOpen={extra.includes(p.id)} />)}
      {more.length > 0 && (
        <select className="input" aria-label="Add a provider" style={{ alignSelf: "flex-start", width: "auto" }} value=""
          onChange={(e) => { if (e.target.value) setExtra((x) => [...x, e.target.value]); }}>
          <option value="">Add a provider…</option>
          {more.map((x) => <option key={x} value={x}>{x}</option>)}
        </select>
      )}
    </section>
  );
}

export default function SettingsPage() {
  const { user, signOut } = useApp();
  const [s, setS] = useState<Settings | null>(null);
  const [current, setCurrent] = useState(SECTIONS[0].id);
  const page = useRef<HTMLDivElement>(null);
  const [sandbox, setSandbox] = useState<SandboxStatus | null>(null);
  const [version, setVersion] = useState("");

  useEffect(() => {
    api.get<Settings>("/settings").then(setS);
    api.get<SandboxStatus>("/sandbox").then(setSandbox).catch(() => {});
    api.get<{ version: string }>("/health").then((h) => setVersion(h.version)).catch(() => {});
  }, []);

  // The section menu follows the scroll: the last section whose top has passed the top of the page.
  const onScroll = () => {
    const top = page.current?.getBoundingClientRect().top ?? 0;
    const el = page.current;
    const atEnd = !!el && el.scrollTop + el.clientHeight >= el.scrollHeight - 4;
    let at = SECTIONS[0].id;
    for (const { id } of SECTIONS) {
      const box = document.getElementById(id)?.getBoundingClientRect();
      if (box && box.top - top <= 96) at = id;
    }
    setCurrent(atEnd ? SECTIONS[SECTIONS.length - 1].id : at);
  };

  if (!s) return <div className="page" />;

  const resetSandbox = async () => {
    if (!confirm("Restart your agent's computer? Running programs stop. Your files are kept.")) return;
    await api.post("/sandbox/reset");
    setSandbox(await api.get<SandboxStatus>("/sandbox"));
  };

  return (
    <>
    <Topbar title="Settings" phoneOnly />
    <div className="page" ref={page} onScroll={onScroll}>
      <div className="settings-layout">
        <nav className="section-nav" aria-label="Settings sections">
          {SECTIONS.map((x) => (
            <a key={x.id} href={`#${x.id}`} className={current === x.id ? "on" : undefined} aria-current={current === x.id ? "true" : undefined}
              onClick={() => setCurrent(x.id)}>{x.label}</a>
          ))}
        </nav>
      <div className="page-inner">
        <PageHeader title="Settings" lead="Choose the models your agent thinks with, and manage your account." />
        <Defaults s={s} onSaved={setS} />
        <Providers s={s} onSaved={setS} />

        <ExternalApps />

        <section className="stack" id="sandbox" aria-labelledby="sandbox-title">
          <h2 id="sandbox-title">Your agent's computer</h2>
          <div className="list">
            <div className="lrow">
              {(sandbox?.state === "running" || sandbox?.state === "ready") && <span className="live-dot" aria-hidden="true" />}
              <div className="grow">
                <div className="title">{sandbox?.kind === "docker" ? "Private container" : "Local folder (development mode)"}</div>
                <div className="meta">
                  {sandbox ? (sandbox.kind === "docker" ? `${sandbox.state === "running" ? "Running" : sandbox.state === "missing" ? "Starts on first use" : sandbox.state} · ${sandbox.image}` : "Commands run directly on the server. Not isolated.") : "Checking…"}
                </div>
              </div>
              {sandbox?.kind === "docker" && <button className="btn sm" onClick={resetSandbox}>Restart</button>}
            </div>
          </div>
        </section>

        <section className="stack" id="account" aria-labelledby="account-title">
          <h2 id="account-title">Account</h2>
          <div className="list">
            <div className="lrow">
              <span className="avatar" aria-hidden="true">{(user.name || user.email)[0]}</span>
              <div className="grow">
                <div className="title">{user.name || user.email}</div>
                <div className="meta">{user.email}</div>
              </div>
              <button className="btn" onClick={signOut}>Sign out</button>
            </div>
          </div>
          {version && <p className="hint" data-testid="app-version">AI Chatbot Framework {version}</p>}
        </section>
      </div>
      </div>
    </div>
    </>
  );
}

import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, type ModelEntry, type ProviderEntry, type Settings } from "../api";
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
  { id: "model-settings", label: "Models" }, { id: "api-keys", label: "API keys" },
  { id: "external-apps", label: "External apps" }, { id: "sandbox", label: "Sandbox" }, { id: "account", label: "Account" },
];
const tokens = (n: number) => (n >= 1_000_000 ? `${+(n / 1_000_000).toFixed(2)}M` : `${Math.round(n / 1000)}K`);
const levels = (m: ModelEntry) => (m.efforts.length ? `effort ${m.efforts.join(", ")}` : "no effort setting");
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
  return { msg, error, run, setError };
}

/** The model new chats start on, and its effort. Each chat can pick another in its message box. */
function Defaults({ s, onSaved }: { s: Settings; onSaved: Update }) {
  const [model, setModel] = useState(s.model);
  const [effort, setEffort] = useState(s.effort);
  const { msg, error, run } = useStatus();
  useEffect(() => { setModel(s.model); setEffort(s.effort); }, [s.model, s.effort]);
  const on = s.models.filter((m) => m.enabled);
  const current = s.models.find((m) => m.key === (model || s.defaults.model));
  const efforts = current?.efforts ?? [];
  const changed = model !== s.model || effort !== s.effort;
  const save = (e: FormEvent) => {
    e.preventDefault();
    run(async () => onSaved(await api.put<Settings>("/settings", { model, effort: efforts.includes(effort) ? effort : "" })));
  };
  const serverDefault = s.models.find((m) => m.key === s.defaults.model)?.name ?? s.defaults.model;
  return (
    <form className="card split" id="model-settings" onSubmit={save} aria-label="Default model settings">
      <div className="card-head">
        <div>
          <h2>Models</h2>
          <span className="model-name" data-testid="model-in-use">{current ? current.key : model || s.defaults.model}{effort && efforts.includes(effort) ? ` · ${effort}` : ""}</span>
        </div>
      </div>
      <div className="card-body">
        <p className="hint" style={{ margin: 0 }}>New chats start on your default model. Each chat can switch model and effort from its message box.</p>
        <div className="grid-2">
          <div className="field">
            <label htmlFor="default-model">Default model</label>
            <select id="default-model" className="input" value={model} onChange={(e) => setModel(e.target.value)}>
              <option value="">Server default ({serverDefault})</option>
              {on.map((m) => <option key={m.key} value={m.key}>{m.name}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="default-effort">Default effort</label>
            <select id="default-effort" className="input" value={efforts.includes(effort) ? effort : ""} disabled={!efforts.length}
              onChange={(e) => setEffort(e.target.value)}>
              <option value="">{efforts.length ? `Model's default (${current?.effort})` : "This model has no effort setting"}</option>
              {efforts.map((x) => <option key={x} value={x}>{x[0].toUpperCase() + x.slice(1)}</option>)}
            </select>
            <span className="hint">More effort: deeper thinking, slower and costlier answers.</span>
          </div>
        </div>
        {error && <div className="banner" role="alert">{error}</div>}
      </div>
      <div className="card-foot">
        <span className="hint">{msg ? <span role="status">{msg}</span> : "Applies to new chats."}</span>
        <button type="button" className="btn ghost" disabled={!changed} onClick={() => { setModel(s.model); setEffort(s.effort); }}>Cancel</button>
        <button className="btn primary" type="submit" disabled={!changed}>Save changes</button>
      </div>
    </form>
  );
}

/** One model in the list: on or off in the model picker, and its token window. */
function ModelRow({ m, s, onSaved }: { m: ModelEntry; s: Settings; onSaved: Update }) {
  const [open, setOpen] = useState(false);
  const [window, setWindow] = useState(m.window && m.window !== m.context_window ? String(m.window) : "");
  const { error, run } = useStatus();
  const isDefault = m.key === (s.model || s.defaults.model);
  const provider = s.providers.find((p) => p.id === m.provider)?.name ?? m.provider;
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
    <div className="lrow" data-testid="model-row">
      <div className="grow">
        <div className="title row-flex wrap">
          {m.name}
          {isDefault && <span className="badge plain">Default</span>}
          {m.custom && <span className="badge plain">Added by you</span>}
          {!m.has_key && <span className="badge warning">No API key</span>}
        </div>
        <div className="meta"><span className="mono">{m.id}</span> · {provider} · {m.window ? `${tokens(m.window)} token window` : "model's own token window"} · {levels(m)}</div>
      </div>
      <div className="side">
        <button type="button" className="btn ghost sm" aria-expanded={open} aria-label={`Edit ${m.name}`} onClick={() => setOpen(!open)}>Edit</button>
        <Toggle label={`Use ${m.name}`} checked={m.enabled} onChange={toggle} />
      </div>
      {open && (
        <form className="model-edit" onSubmit={saveWindow} aria-label={`${m.name} settings`}>
          <div className="field">
            <label htmlFor={`window-${m.key}`}>Token window</label>
            <input id={`window-${m.key}`} className="input mono" inputMode="numeric" value={window}
              onChange={(e) => setWindow(e.target.value.replace(/[^0-9]/g, ""))}
              placeholder={m.context_window ? String(m.context_window) : "The model's own"} />
            <span className="hint">
              How much of the conversation the model sees. Older messages are summarised at 80% of it.
              {m.max_context_window ? ` Up to ${m.max_context_window.toLocaleString("en-US")} tokens.` : ""}
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

function ModelList({ s, onSaved }: { s: Settings; onSaved: Update }) {
  const [query, setQuery] = useState("");
  const [provider, setProvider] = useState(s.defaults.provider);
  const [id, setId] = useState("");
  const { error, run } = useStatus();
  const q = query.trim().toLowerCase();
  const shown = s.models.filter((m) => !q || `${m.name} ${m.key}`.toLowerCase().includes(q));
  const add = (e: FormEvent) => {
    e.preventDefault();
    run(async () => { onSaved(await api.post<Settings>("/settings/models", { provider, id: id.trim() })); setId(""); });
  };
  return (
    <section className="stack" aria-labelledby="model-list">
      <div>
        <h3 id="model-list">Model list</h3>
        <p className="lead">Models that are on show up in each chat's model picker.</p>
      </div>
      <input className="input" type="search" aria-label="Search models" placeholder="Search models" value={query} onChange={(e) => setQuery(e.target.value)} />
      <div className="list">
        {shown.map((m) => <ModelRow key={m.key} m={m} s={s} onSaved={onSaved} />)}
        {!shown.length && <p className="empty">No model matches “{query}”.</p>}
      </div>
      {s.custom_models && (
        <form className="row-flex wrap" onSubmit={add} aria-label="Add a model">
          <select className="input" aria-label="Provider of the new model" style={{ width: "auto" }} value={provider} onChange={(e) => setProvider(e.target.value)}>
            {s.allowed_providers.map((p) => <option key={p} value={p}>{s.providers.find((x) => x.id === p)?.name ?? p}</option>)}
          </select>
          <input className="input mono grow-input" aria-label="Model id" placeholder="Model id, e.g. llama3.1:8b" value={id} onChange={(e) => setId(e.target.value)} />
          <button className="btn" type="submit" disabled={!id.trim()}>Add model</button>
        </form>
      )}
      {error && <div className="banner" role="alert">{error}</div>}
    </section>
  );
}

/** The user's key and, optionally, server address for one provider. */
function ProviderKey({ p, s, onSaved }: { p: ProviderEntry; s: Settings; onSaved: Update }) {
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState(p.base_url);
  const [advanced, setAdvanced] = useState(!!p.base_url);
  const { msg, error, run } = useStatus();
  useEffect(() => setBaseUrl(p.base_url), [p.base_url]);
  // The server's key only goes to the server's own provider and address.
  const serverKey = s.defaults.has_api_key && p.id === s.defaults.provider && ["", trim(s.defaults.base_url)].includes(trim(baseUrl));
  const put = (key: string | null) => api.put<Settings>(`/settings/providers/${p.id}`, { base_url: baseUrl, api_key: key });
  const save = (e: FormEvent) => {
    e.preventDefault();
    run(async () => { onSaved(await put(apiKey || null)); setApiKey(""); });
  };
  const showAddress = advanced || p.id === "openai" || !!baseUrl;
  const changed = !!apiKey || baseUrl !== p.base_url;
  return (
    <form className="card" onSubmit={save} aria-label={`${p.name} key`}>
      <div className="card-head">
        <h3>{p.name}</h3>
        {p.has_api_key ? <span className="badge success">Key saved</span> : serverKey ? <span className="badge plain">Server's key</span> : null}
      </div>
      <div className="field">
        <label htmlFor={`key-${p.id}`}>{p.name} API key</label>
        <input id={`key-${p.id}`} className="input" type="password" autoComplete="off" value={apiKey} onChange={(e) => setApiKey(e.target.value)}
          placeholder={p.has_api_key ? "•••••••• (saved)" : serverKey ? "Using the server's key" : "Paste your API key"} />
        {!p.has_api_key && !serverKey && s.defaults.has_api_key && p.id === s.defaults.provider &&
          <span className="hint">The server's key only works with its own model provider and address. Add your own key for this one.</span>}
      </div>
      {showAddress ? (
        <div className="field">
          <label htmlFor={`url-${p.id}`}>{p.name} server address <span className="hint">(optional)</span></label>
          <input id={`url-${p.id}`} className="input mono" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)}
            placeholder={p.id === "openai" ? "http://localhost:11434/v1 (Ollama, OpenRouter, vLLM…)" : "https://…"} />
          <span className="hint">Only for models served from your own or another company's server.</span>
        </div>
      ) : (
        <button type="button" className="btn ghost" style={{ alignSelf: "flex-start" }} onClick={() => setAdvanced(true)}>Use a custom server address</button>
      )}
      {error && <div className="banner" role="alert">{error}</div>}
      <div className="row-flex end wrap">
        {msg && <span className="hint" role="status" style={{ marginRight: "auto" }}>{msg}</span>}
        {p.has_api_key && <button type="button" className="btn ghost sm" onClick={() => run(async () => onSaved(await put("")), "Key removed")}>Remove saved key</button>}
        <button className="btn" type="submit" disabled={!changed}>Save {p.name} key</button>
      </div>
    </form>
  );
}

function ApiKeys({ s, onSaved }: { s: Settings; onSaved: Update }) {
  const [extra, setExtra] = useState<string[]>([]);
  const listed = [...s.providers, ...extra.filter((x) => !s.providers.some((p) => p.id === x))
    .map((x) => ({ id: x, name: x, base_url: "", has_api_key: false, server: false }))];
  const more = s.allowed_providers.filter((x) => x !== "*" && !listed.some((p) => p.id === x));
  return (
    <section className="stack" id="api-keys" aria-labelledby="api-keys-title">
      <div>
        <h2 id="api-keys-title">API keys</h2>
        <p className="lead">Your key for each model provider. Keys are stored encrypted and only sent to that provider.</p>
      </div>
      {listed.map((p) => <ProviderKey key={p.id} p={p} s={s} onSaved={onSaved} />)}
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
    if (!confirm("Restart your sandbox? Running programs stop. Your files are kept.")) return;
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
        <ModelList s={s} onSaved={setS} />
        <ApiKeys s={s} onSaved={setS} />

        <ExternalApps />

        <section className="stack" id="sandbox" aria-labelledby="sandbox-title">
          <h2 id="sandbox-title">Sandbox</h2>
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

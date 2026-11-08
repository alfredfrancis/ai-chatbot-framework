import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, type Settings } from "../api";
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

const PROVIDERS = [
  { value: "", label: "Server default", hint: "" },
  { value: "anthropic", label: "Claude", hint: "From Anthropic" },
  { value: "openai", label: "OpenAI-compatible", hint: "OpenAI, Ollama, OpenRouter, vLLM" },
  { value: "other", label: "Another provider", hint: "Any LangChain provider" },
];
const SECTIONS = [
  { id: "model-settings", label: "Model" }, { id: "external-apps", label: "External apps" },
  { id: "sandbox", label: "Sandbox" }, { id: "account", label: "Account" },
];
const KNOWN = ["", "anthropic", "openai"];

export default function SettingsPage() {
  const { user, signOut } = useApp();
  const [s, setS] = useState<Settings | null>(null);
  const [advanced, setAdvanced] = useState(false);
  const [current, setCurrent] = useState(SECTIONS[0].id);
  const page = useRef<HTMLDivElement>(null);
  const [provider, setProvider] = useState("");
  const [custom, setCustom] = useState("");
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [sandbox, setSandbox] = useState<SandboxStatus | null>(null);

  const reset = (r: Settings) => {
    setProvider(KNOWN.includes(r.provider) ? r.provider : "other");
    setCustom(KNOWN.includes(r.provider) ? "" : r.provider);
    setModel(r.model);
    setBaseUrl(r.base_url);
    setApiKey("");
    setError("");
  };
  useEffect(() => {
    api.get<Settings>("/settings").then((r) => { setS(r); reset(r); });
    api.get<SandboxStatus>("/sandbox").then(setSandbox).catch(() => {});
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

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const r = await api.put<Settings>("/settings", { provider: provider === "other" ? custom.trim() : provider, model, base_url: baseUrl, api_key: apiKey || null });
      setS(r);
      setApiKey("");
      setMsg("Saved");
      setTimeout(() => setMsg(""), 2000);
    } catch (err) {
      setError((err as Error).message);
    }
  };
  const clearKey = async () => {
    setS(await api.put<Settings>("/settings", { provider: provider === "other" ? custom.trim() : provider, model, base_url: baseUrl, api_key: "" }));
  };
  const resetSandbox = async () => {
    if (!confirm("Restart your sandbox? Running programs stop. Your files are kept.")) return;
    await api.post("/sandbox/reset");
    setSandbox(await api.get<SandboxStatus>("/sandbox"));
  };

  const effective = provider || s.defaults.provider;
  // The server's key only goes to the server's own provider and address.
  const trim = (u: string) => u.trim().replace(/\/+$/, "");
  const serverKey = s.defaults.has_api_key && effective === s.defaults.provider && ["", trim(s.defaults.base_url)].includes(trim(baseUrl));
  const changed = (provider === "other" ? custom.trim() : provider) !== s.provider || model !== s.model || baseUrl !== s.base_url || !!apiKey;
  const showAddress = advanced || provider === "openai" || provider === "other" || !!s.base_url || !!baseUrl;
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
        <PageHeader title="Settings" lead="Choose the model your agent thinks with, and manage your account." />
        <form className="card split" id="model-settings" onSubmit={save} aria-label="Model settings">
          <div className="card-head">
            <div>
              <h2>Model</h2>
              <span className="model-name" data-testid="model-in-use">{effective || "default"} · {model || (effective === s.defaults.provider ? s.defaults.model : "default model")}</span>
            </div>
          </div>
          <div className="card-body">
            <fieldset className="choices">
              <legend className="label">Provider</legend>
              {PROVIDERS.map((p) => (
                <label key={p.value} className={`choice${provider === p.value ? " on" : ""}`}>
                  <input type="radio" name="provider" value={p.value} checked={provider === p.value} onChange={() => setProvider(p.value)} />
                  <span className="text">
                    <span className="title">{p.label}</span>
                    <span className="meta">{p.value === "" ? `${s.defaults.provider} · ${s.defaults.model}` : p.hint}</span>
                  </span>
                </label>
              ))}
            </fieldset>
            {provider === "other" && (
              <div className="field">
                <label htmlFor="custom-provider">LangChain provider id</label>
                <input id="custom-provider" className="input" value={custom} onChange={(e) => setCustom(e.target.value)} placeholder="ollama, google_genai, bedrock_converse…" />
                <span className="hint">The matching langchain-&lt;provider&gt; package must be installed on the server.</span>
              </div>
            )}
            <div className="grid-2">
              <div className="field">
                <label htmlFor="model">Model</label>
                <input id="model" className="input mono" value={model} onChange={(e) => setModel(e.target.value)}
                  placeholder={effective === s.defaults.provider ? s.defaults.model : effective === "anthropic" ? "claude-opus-5-5" : "gpt-4.1-mini"} />
              </div>
              <div className="field">
                <label htmlFor="api-key">API key</label>
                <input id="api-key" className="input" type="password" autoComplete="off" value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={s.has_api_key ? "•••••••• (saved)" : serverKey ? "Using the server's key" : "Paste your API key"} />
                {!s.has_api_key && !serverKey && s.defaults.has_api_key && <span className="hint">The server's key only works with its own model provider and address. Add your own key for this one.</span>}
                {s.has_api_key && <button type="button" className="btn ghost sm" style={{ alignSelf: "flex-start" }} onClick={clearKey}>Remove saved key</button>}
              </div>
            </div>
            {showAddress ? (
              <div className="field">
                <label htmlFor="base-url">Server address <span className="hint">(optional)</span></label>
                <input id="base-url" className="input mono" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder={effective === "openai" ? "http://localhost:11434/v1" : "https://api.anthropic.com"} />
                <span className="hint">Only for a model served from your own or another company's server.</span>
              </div>
            ) : (
              <button type="button" className="btn ghost" style={{ alignSelf: "flex-start" }} onClick={() => setAdvanced(true)}>Use a custom server address</button>
            )}
            {error && <div className="banner" role="alert">{error}</div>}
          </div>
          <div className="card-foot">
            <span className="hint">{msg ? <span role="status">{msg}</span> : "Applies to new messages."}</span>
            <button type="button" className="btn ghost" disabled={!changed} onClick={() => reset(s)}>Cancel</button>
            <button className="btn primary" type="submit">Save changes</button>
          </div>
        </form>

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
        </section>
      </div>
      </div>
    </div>
    </>
  );
}

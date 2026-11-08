import { useEffect, useState, type FormEvent } from "react";
import { api, type Settings } from "../api";
import { Topbar } from "../App";

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
            <button type="button" className={`btn ${state.token ? "sm" : "primary"}`} onClick={create}>{state.token ? "Replace token" : "Create access token"}</button>
          </span>
        </div>
      </div>
    </section>
  );
}

const PROVIDERS = [
  { value: "", label: "Server default", hint: "" },
  { value: "anthropic", label: "Claude (Anthropic)", hint: "anthropic" },
  { value: "openai", label: "OpenAI-compatible", hint: "openai, ollama, openrouter…" },
  { value: "other", label: "Another provider", hint: "any langchain id" },
];
const KNOWN = ["", "anthropic", "openai"];

export default function SettingsPage() {
  const [s, setS] = useState<Settings | null>(null);
  const [provider, setProvider] = useState("");
  const [custom, setCustom] = useState("");
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [sandbox, setSandbox] = useState<SandboxStatus | null>(null);

  useEffect(() => {
    api.get<Settings>("/settings").then((r) => {
      setS(r);
      setProvider(KNOWN.includes(r.provider) ? r.provider : "other");
      setCustom(KNOWN.includes(r.provider) ? "" : r.provider);
      setModel(r.model);
      setBaseUrl(r.base_url);
    });
    api.get<SandboxStatus>("/sandbox").then(setSandbox).catch(() => {});
  }, []);

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
  return (
    <>
    <Topbar title="Settings" />
    <div className="page">
      <div className="settings-layout">
        <nav className="section-nav" aria-label="Settings sections">
          <a href="#model-settings">Model</a><a href="#external-apps">External apps</a><a href="#sandbox">Sandbox</a>
        </nav>
      <div className="page-inner">
        <div>
          <h1>Settings</h1>
          <p className="lead">Choose the model your agent uses. Leave fields empty to use the server's defaults.</p>
        </div>
        <form className="card" id="model-settings" onSubmit={save} aria-label="Model settings">
          <div className="row-flex between wrap">
            <h2>Model</h2>
            <span className="badge live" data-testid="model-in-use">{effective || "default"} · {model || (effective === s.defaults.provider ? s.defaults.model : "default model")}</span>
          </div>
          <fieldset className="choices">
            <legend className="label">Model provider</legend>
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
              <input id="model" className="input" value={model} onChange={(e) => setModel(e.target.value)}
                placeholder={effective === s.defaults.provider ? s.defaults.model : effective === "anthropic" ? "claude-opus-5-5" : "gpt-4.1-mini"} />
            </div>
            <div className="field">
              <label htmlFor="base-url">Server address <span className="hint">(optional)</span></label>
              <input id="base-url" className="input" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)}
                placeholder={effective === "openai" ? "http://localhost:11434/v1" : "https://api.anthropic.com"} />
            </div>
          </div>
          <div className="field">
            <label htmlFor="api-key">API key</label>
            <input id="api-key" className="input" type="password" autoComplete="off" value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={s.has_api_key ? "•••••••• (saved)" : serverKey ? "Using the server's key" : "Paste your API key"} />
            {!s.has_api_key && !serverKey && s.defaults.has_api_key && <span className="hint">The server's key only works with its own model provider and address. Add your own key for this one.</span>}
            {s.has_api_key && <button type="button" className="btn ghost sm" style={{ alignSelf: "flex-start" }} onClick={clearKey}>Remove saved key</button>}
          </div>
          {error && <div className="banner" role="alert">{error}</div>}
          <div className="row-flex end">
            {msg && <span className="hint" role="status">{msg}</span>}
            <button className="btn primary" type="submit">Save</button>
          </div>
        </form>

        <ExternalApps />

        <section className="stack" id="sandbox">
          <h2>Sandbox</h2>
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
      </div>
      </div>
    </div>
    </>
  );
}

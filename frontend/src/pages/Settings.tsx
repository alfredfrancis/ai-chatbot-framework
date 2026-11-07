import { useEffect, useState, type FormEvent } from "react";
import { api, type Settings } from "../api";

type SandboxStatus = { kind: string; state: string; name?: string; image?: string };

const PROVIDERS = [
  { value: "", label: "Server default" },
  { value: "anthropic", label: "Claude (Anthropic)" },
  { value: "openai", label: "OpenAI-compatible (OpenAI, Ollama, OpenRouter…)" },
];

export default function SettingsPage() {
  const [s, setS] = useState<Settings | null>(null);
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [sandbox, setSandbox] = useState<SandboxStatus | null>(null);

  useEffect(() => {
    api.get<Settings>("/settings").then((r) => {
      setS(r);
      setProvider(r.provider);
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
      const r = await api.put<Settings>("/settings", { provider, model, base_url: baseUrl, api_key: apiKey || null });
      setS(r);
      setApiKey("");
      setMsg("Saved");
      setTimeout(() => setMsg(""), 2000);
    } catch (err) {
      setError((err as Error).message);
    }
  };
  const clearKey = async () => {
    setS(await api.put<Settings>("/settings", { provider, model, base_url: baseUrl, api_key: "" }));
  };
  const resetSandbox = async () => {
    if (!confirm("Restart your sandbox? Running programs stop. Your files are kept.")) return;
    await api.post("/sandbox/reset");
    setSandbox(await api.get<SandboxStatus>("/sandbox"));
  };

  const effective = provider || s.defaults.provider;
  return (
    <div className="page">
      <div className="page-inner">
        <div>
          <h1>Settings</h1>
          <p className="lead">Choose the AI model Harbor uses. Leave fields empty to use the server's defaults.</p>
        </div>
        <form className="card" onSubmit={save} aria-label="Model settings">
          <div className="field">
            <label htmlFor="provider">Model provider</label>
            <select id="provider" className="select" value={provider} onChange={(e) => setProvider(e.target.value)}>
              {PROVIDERS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
          </div>
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
              placeholder={s.has_api_key ? "•••••••• (saved)" : s.defaults.has_api_key ? "Using the server's key" : "Paste your API key"} />
            {s.has_api_key && <button type="button" className="btn ghost small" style={{ alignSelf: "flex-start" }} onClick={clearKey}>Remove saved key</button>}
          </div>
          {error && <div className="banner" role="alert">{error}</div>}
          <div className="row end">
            {msg && <span className="hint" role="status">{msg}</span>}
            <button className="btn" type="submit">Save</button>
          </div>
        </form>

        <section className="stack">
          <h2>Sandbox</h2>
          <div className="list">
            <div className="list-item">
              <div className="grow">
                <div className="title">{sandbox?.kind === "docker" ? "Private container" : "Local folder (development mode)"}</div>
                <div className="sub">
                  {sandbox ? (sandbox.kind === "docker" ? `${sandbox.state === "running" ? "Running" : sandbox.state === "missing" ? "Starts on first use" : sandbox.state} · ${sandbox.image}` : "Commands run directly on the server. Not isolated.") : "Checking…"}
                </div>
              </div>
              {sandbox?.kind === "docker" && <button className="btn secondary small" onClick={resetSandbox}>Restart</button>}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

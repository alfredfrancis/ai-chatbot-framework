import { useCallback, useEffect, useState } from "react";
import { api, type McpServer } from "../api";

const EXAMPLE = `{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]
    },
    "linear": { "url": "https://mcp.linear.app/mcp" }
  }
}
`;

const TINTS = [
  ["#E8F1FC", "#0058B0"], ["#F2EEFC", "#5B32B4"], ["#EEF6EF", "#1A7F37"], ["#FDF1E7", "#A04A00"],
];

function tint(name: string) {
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return TINTS[h % TINTS.length];
}

/** Open the provider's sign-in page in a popup; resolves when the callback page reports back. */
function signInPopup(url: string): Promise<boolean> {
  return new Promise((resolve) => {
    const popup = window.open(url, "acf-oauth", "width=520,height=700");
    if (!popup) {
      window.location.href = url; // popup blocked: do the redirect in this tab
      return;
    }
    const onMessage = (e: MessageEvent) => {
      if (e.origin !== window.location.origin || e.data?.type !== "acf-oauth") return;
      cleanup();
      resolve(!!e.data.ok);
    };
    const timer = setInterval(() => {
      if (popup.closed) { cleanup(); resolve(false); }
    }, 500);
    const cleanup = () => { window.removeEventListener("message", onMessage); clearInterval(timer); };
    window.addEventListener("message", onMessage);
  });
}

function ServerRow({ s, onChange }: { s: McpServer; onChange: () => void }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [bg, fg] = tint(s.name);

  const signIn = async () => {
    setBusy(true);
    setErr("");
    try {
      const { authorize_url } = await api.post<{ authorize_url: string }>(`/mcp/servers/${s.name}/oauth/start`, {
        redirect_uri: `${window.location.origin}/oauth/callback`,
      });
      await signInPopup(authorize_url);
      onChange();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const signOut = async () => {
    await api.del(`/mcp/servers/${s.name}/oauth`);
    onChange();
  };

  const where = s.transport === "stdio" ? "Runs in your sandbox" : "Remote";
  return (
    <div className="list-item" data-testid={`server-${s.name}`}>
      <div className="avatar" style={{ background: bg, color: fg }} aria-hidden="true">{s.name[0]}</div>
      <div className="grow">
        <div className="title">{s.name}</div>
        <div className="sub">
          {where}
          {s.state === "connected" && ` · ${s.tools.length} tool${s.tools.length === 1 ? "" : "s"}`}
        </div>
        {s.state === "error" && <div className="error-text">{s.error}</div>}
        {err && <div className="error-text">{err}</div>}
        {s.state === "connected" && s.tools.length > 0 && (
          <details className="tools">
            <summary>Show tools</summary>
            <ul>{s.tools.map((t) => <li key={t.name}><strong>{t.name}</strong>{t.description ? ` — ${t.description}` : ""}</li>)}</ul>
          </details>
        )}
      </div>
      {s.state === "connected" && <span className="status ok"><span className="dot" />Connected</span>}
      {s.state === "error" && <span className="status bad"><span className="dot" />Not working</span>}
      {s.state === "disabled" && <span className="status"><span className="dot" />Off</span>}
      {s.state === "needs_auth" && <button className="btn small" onClick={signIn} disabled={busy}>{busy ? "Waiting…" : "Sign in"}</button>}
      {s.state === "connected" && s.signed_in && <button className="btn ghost small" onClick={signOut}>Sign out</button>}
    </div>
  );
}

export default function ConnectionsPage() {
  const [servers, setServers] = useState<McpServer[] | null>(null);
  const [config, setConfig] = useState("");
  const [saved, setSaved] = useState("");
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  const refresh = useCallback(async () => {
    setServers(null);
    const r = await api.get<{ error: string | null; servers: McpServer[] }>("/mcp/servers");
    setServers(r.servers);
  }, []);

  useEffect(() => {
    api.get<{ config: string }>("/mcp/config").then((r) => { setConfig(r.config); setSaved(r.config); });
    refresh();
  }, [refresh]);

  const save = async () => {
    setError("");
    setMsg("");
    try {
      await api.put("/mcp/config", { config });
      setSaved(config);
      setMsg("Saved");
      refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="page">
      <div className="page-inner">
        <div>
          <h1>Connections</h1>
          <p className="lead">Give your agent access to apps and tools. Local tools run inside your private sandbox.</p>
        </div>

        <section aria-label="Connected servers">
          {servers === null ? (
            <div className="list"><div className="empty">Checking connections…</div></div>
          ) : servers.length === 0 ? (
            <div className="list"><div className="empty">No connections yet. Add one below.</div></div>
          ) : (
            <div className="list">{servers.map((s) => <ServerRow key={s.name} s={s} onChange={refresh} />)}</div>
          )}
        </section>

        <section className="stack">
          <div className="row between">
            <h2><label htmlFor="mcp-config">Configuration</label></h2>
            <span className="hint">Same format as Claude Desktop</span>
          </div>
          <textarea id="mcp-config" className="textarea code" rows={12} spellCheck={false} value={config}
            onChange={(e) => setConfig(e.target.value)} />
          {error && <div className="banner" role="alert">{error}</div>}
          <div className="row between">
            <button className="btn ghost small" onClick={() => setConfig(EXAMPLE)}>Insert example</button>
            <div className="row">
              {msg && <span className="hint" role="status">{msg}</span>}
              <button className="btn" onClick={save} disabled={config === saved}>Save</button>
            </div>
          </div>
          <p className="hint">
            Use <code>"command"</code> for tools that run in your sandbox (like <code>npx</code> or <code>uvx</code> servers)
            and <code>"url"</code> for online services. If a service needs you to sign in, a Sign in button appears above.
          </p>
        </section>
      </div>
    </div>
  );
}

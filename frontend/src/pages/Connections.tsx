import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, type McpPreset, type McpServer } from "../api";
import { PageHeader, Topbar, useApp } from "../App";
import { MoreMenu } from "../components/Menu";
import { Toggle } from "../components/Toggle";

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

type Entry = { command?: string; args?: string[]; env?: Record<string, string>; url?: string; headers?: Record<string, string>; enabled?: boolean; disabled?: boolean };
type Draft = { name: string; transport: "stdio" | "http"; command: string; args: string; env: string; url: string; headers: string; enabled: boolean };

const EMPTY: Draft = { name: "", transport: "stdio", command: "", args: "", env: "", url: "", headers: "", enabled: true };

function parseEntries(config: string): Record<string, Entry> | null {
  try {
    const data = JSON.parse(config || "{}");
    return data && typeof data.mcpServers === "object" && data.mcpServers ? data.mcpServers : {};
  } catch {
    return null;
  }
}

function toDraft(name: string, e: Entry): Draft {
  const pairs = (o: Record<string, string> | undefined, sep: string) => Object.entries(o ?? {}).map(([k, v]) => `${k}${sep}${v}`).join("\n");
  return {
    name,
    transport: e.url ? "http" : "stdio",
    command: e.command ?? "",
    args: (e.args ?? []).join("\n"),
    env: pairs(e.env, "="),
    url: e.url ?? "",
    headers: pairs(e.headers, ": "),
    enabled: e.enabled !== false && e.disabled !== true,
  };
}

/** "KEY=value" (or "Name: value") lines → object. Throws a readable error for a bad line. */
function parsePairs(text: string, sep: string, what: string, example: string): Record<string, string> {
  const out: Record<string, string> = {};
  text.split("\n").forEach((line, i) => {
    if (!line.trim()) return;
    const at = line.indexOf(sep);
    const key = at > 0 ? line.slice(0, at).trim() : "";
    if (!key) throw new Error(`${what} line ${i + 1}: use ${example}`);
    out[key] = line.slice(at + 1).trim();
  });
  return out;
}

function ServerForm({ initial, editing, onDone, onCancel }: { initial: Draft; editing: string | null; onDone: () => void; onCancel: () => void }) {
  const [d, setD] = useState<Draft>(initial);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setD((x) => ({ ...x, [k]: v }));
  const title = editing ? `Edit ${editing}` : "New connection";

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const name = d.name.trim();
      const body = d.transport === "stdio"
        ? { transport: "stdio", command: d.command, args: d.args.split("\n").map((a) => a.trim()).filter(Boolean),
            env: parsePairs(d.env, "=", "Environment variables", "NAME=value") }
        : { transport: "http", url: d.url, headers: parsePairs(d.headers, ":", "Headers", "Name: value") };
      await api.put(`/mcp/servers/${encodeURIComponent(name)}`, { ...body, enabled: d.enabled, rename_from: editing });
      onDone();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="card" onSubmit={submit} aria-label={title}>
      <h2>{title}</h2>
      <div className="grid-2">
        <div className="field">
          <label htmlFor="mcp-name">Name</label>
          <input id="mcp-name" className="input" required maxLength={40} value={d.name} onChange={(e) => set("name", e.target.value)}
            placeholder="filesystem" autoComplete="off" spellCheck={false} />
        </div>
        <div className="field">
          <label htmlFor="mcp-type">Type</label>
          <select id="mcp-type" className="input" value={d.transport} onChange={(e) => set("transport", e.target.value as Draft["transport"])}>
            <option value="stdio">Runs on your agent's computer (command)</option>
            <option value="http">Online service (URL)</option>
          </select>
        </div>
      </div>
      {d.transport === "stdio" ? (
        <>
          <div className="field">
            <label htmlFor="mcp-command">Command</label>
            <input id="mcp-command" className="input mono" required value={d.command} onChange={(e) => set("command", e.target.value)}
              placeholder="npx" spellCheck={false} />
          </div>
          <div className="field">
            <label htmlFor="mcp-args">Arguments</label>
            <textarea id="mcp-args" className="input mono" rows={3} value={d.args} onChange={(e) => set("args", e.target.value)}
              placeholder={"-y\n@modelcontextprotocol/server-filesystem\n/workspace"} spellCheck={false} />
            <span className="hint">One per line.</span>
          </div>
          <div className="field">
            <label htmlFor="mcp-env">Environment variables</label>
            <textarea id="mcp-env" className="input mono" rows={2} value={d.env} onChange={(e) => set("env", e.target.value)}
              placeholder="API_KEY=…" spellCheck={false} />
            <span className="hint">One <code>NAME=value</code> per line. Optional.</span>
          </div>
        </>
      ) : (
        <>
          <div className="field">
            <label htmlFor="mcp-url">URL</label>
            <input id="mcp-url" className="input mono" type="url" required value={d.url} onChange={(e) => set("url", e.target.value)}
              placeholder="https://mcp.example.com/mcp" spellCheck={false} />
          </div>
          <div className="field">
            <label htmlFor="mcp-headers">Headers</label>
            <textarea id="mcp-headers" className="input mono" rows={2} value={d.headers} onChange={(e) => set("headers", e.target.value)}
              placeholder="X-Api-Key: …" spellCheck={false} />
            <span className="hint">One <code>Name: value</code> per line. Optional — if the service needs you to sign in, a Sign in button appears after saving.</span>
          </div>
        </>
      )}
      <div className="row-flex">
        <Toggle id="mcp-enabled" checked={d.enabled} onChange={(v) => set("enabled", v)} label="Turned on" />
        <label htmlFor="mcp-enabled">Turned on</label>
      </div>
      {error && <div className="banner" role="alert">{error}</div>}
      <div className="row-flex end">
        <button type="button" className="btn ghost" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn primary" disabled={busy}>{editing ? "Save changes" : "Add connection"}</button>
      </div>
    </form>
  );
}

function ServerRow({ s, editable, onChange, onEdit, onDelete }: {
  s: McpServer; editable: boolean; onChange: () => void; onEdit: () => void; onDelete: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

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

  const where = s.transport === "stdio" ? "Runs on your agent's computer" : "Remote";
  return (
    <div className="lrow" data-testid={`server-${s.name}`}>
      <div className="grow">
        <div className="title">{s.name}</div>
        <div className="meta">
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
      {s.state === "connected" && <span className="badge success">Connected</span>}
      {s.state === "error" && <span className="badge danger">Not working</span>}
      {s.state === "disabled" && <span className="badge">Off</span>}
      {s.state === "needs_auth" && <span className="badge warning">Needs sign-in</span>}
      {s.state === "needs_auth" && <button className="btn primary sm" onClick={signIn} disabled={busy}>{busy ? "Waiting…" : "Sign in"}</button>}
      {s.state === "connected" && s.signed_in && <button className="btn ghost sm" onClick={signOut}>Sign out</button>}
      {editable && (
        <div className="side">
          <MoreMenu label={`More actions for ${s.name}`} items={[
            { label: "Edit", onSelect: onEdit },
            { label: "Delete connection", confirm: "Yes, delete this connection", onSelect: onDelete },
          ]} />
        </div>
      )}
    </div>
  );
}

function PresetCard({ p, onAdd }: { p: McpPreset; onAdd: (p: McpPreset) => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const add = async () => {
    setBusy(true);
    try { await onAdd(p); } finally { setBusy(false); }
  };
  return (
    <div className="lrow" data-testid={`preset-${p.id}`}>
      <div className="grow"><span className="title">{p.name}</span><span className="meta">{p.description}</span></div>
      <div className="side">
        {p.added
          ? <span className="badge success">Added</span>
          : <button className="btn sm" onClick={add} disabled={busy} aria-label={`Connect ${p.name}`}>{busy ? "Connecting…" : "Connect"}</button>}
      </div>
    </div>
  );
}

export default function ConnectionsPage() {
  const { refresh: refreshApp } = useApp();
  const [servers, setServers] = useState<McpServer[] | null>(null);
  const [listError, setListError] = useState("");
  const [config, setConfig] = useState("");
  const [saved, setSaved] = useState("");
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [view, setView] = useState<"form" | "json">("form");
  const [editing, setEditing] = useState<{ name: string | null; draft: Draft } | null>(null);
  const [presets, setPresets] = useState<McpPreset[]>([]);
  const [presetError, setPresetError] = useState("");

  const refresh = useCallback(async () => {
    setServers(null);
    const [c, r, p] = await Promise.all([
      api.get<{ config: string }>("/mcp/config"),
      api.get<{ error: string | null; servers: McpServer[] }>("/mcp/servers"),
      api.get<{ presets: McpPreset[] }>("/mcp/presets"),
    ]);
    setPresets(p.presets);
    setConfig(c.config);
    setSaved(c.config);
    setListError(r.error ?? "");
    setServers(r.servers);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const entries = parseEntries(saved);
  const changed = () => { refreshApp(); refresh(); };

  const saveJson = async () => {
    setError("");
    setMsg("");
    try {
      await api.put("/mcp/config", { config });
      setMsg("Saved");
      changed();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const addPreset = async (p: McpPreset) => {
    setPresetError("");
    try {
      await api.post(`/mcp/presets/${encodeURIComponent(p.id)}`, {});
      changed();
    } catch (e) {
      setPresetError((e as Error).message);
    }
  };
  const remove = async (name: string) => {
    await api.del(`/mcp/servers/${encodeURIComponent(name)}`);
    changed();
  };
  const switchView = (v: "form" | "json") => {
    setView(v);
    setEditing(null);
    setError("");
    setMsg("");
    if (v === "form") setConfig(saved); // drop unsaved JSON edits
  };

  const hasServers = !!servers?.length;
  return (
    <>
    <Topbar title="Connections" phoneOnly />
    <div className="page">
      <div className="page-inner">
        <PageHeader title="Connections" lead="Connect the apps you use, and your agent can work with them in any chat.">
          {view === "json" && <button className="btn" onClick={() => switchView("form")}>Back to connections</button>}
        </PageHeader>

        {view === "form" ? (
          <>
            {editing && (
              <ServerForm key={editing.name ?? ""} initial={editing.draft} editing={editing.name}
                onCancel={() => setEditing(null)} onDone={() => { setEditing(null); changed(); }} />
            )}
            {(listError || !entries) && (
              <div className="banner" role="alert">
                {listError || "The configuration isn't valid JSON."} Fix it with Edit as JSON.
              </div>
            )}
            {servers === null ? (
              <div className="list"><div className="empty">Checking connections…</div></div>
            ) : hasServers && (
              <section className="stack" aria-labelledby="your-connections">
                <h2 id="your-connections">Your connections</h2>
                <div className="list">
                  {servers.map((s) => (
                    <ServerRow key={s.name} s={s} onChange={refresh} editable={!!entries?.[s.name] && !editing}
                      onEdit={() => entries && setEditing({ name: s.name, draft: toDraft(s.name, entries[s.name]) })}
                      onDelete={() => remove(s.name)} />
                  ))}
                </div>
              </section>
            )}
            {servers !== null && !hasServers && presets.length === 0 && (
              <div className="list"><div className="empty">No connections yet. Add one to give your agent new tools.</div></div>
            )}

            {presets.length > 0 && (
              <section className="stack" aria-label="Popular apps">
                <div className="row-flex between wrap">
                  <h2>{hasServers ? "Popular apps" : "Connect your first app"}</h2>
                  <span className="hint">You sign in with your own account. No API keys.</span>
                </div>
                {presetError && <div className="banner" role="alert">{presetError}</div>}
                <div className="list app-list">{presets.map((p) => <PresetCard key={p.id} p={p} onAdd={addPreset} />)}</div>
              </section>
            )}

            {!editing && (
              <section className="more-tools" aria-labelledby="more-tools">
                <div>
                  <h2 className="subhead" id="more-tools">Another app or tool</h2>
                  <p className="hint">Add another app by its address (an MCP server), or run one on your agent's computer.</p>
                </div>
                <div className="row-flex">
                  <button className="btn ghost" onClick={() => switchView("json")}>Edit as JSON</button>
                  <button className="btn" disabled={!entries} onClick={() => setEditing({ name: null, draft: EMPTY })}>Add custom connection</button>
                </div>
              </section>
            )}
          </>
        ) : (
          <section className="stack">
            <div className="row-flex between wrap">
              <label className="label" htmlFor="mcp-config">Configuration (JSON)</label>
              <span className="hint">Same format as Claude Desktop</span>
            </div>
            <textarea id="mcp-config" className="input mono" rows={14} spellCheck={false} value={config}
              onChange={(e) => setConfig(e.target.value)} />
            {error && <div className="banner" role="alert">{error}</div>}
            <div className="row-flex between">
              <button className="btn ghost sm" onClick={() => setConfig(EXAMPLE)}>Insert example</button>
              <div className="row-flex">
                {msg && <span className="hint" role="status">{msg}</span>}
                <button className="btn primary" onClick={saveJson} disabled={config === saved}>Save</button>
              </div>
            </div>
            <p className="hint">
              Use <code>"command"</code> for tools that run on your agent's computer (like <code>npx</code> or <code>uvx</code> servers)
              and <code>"url"</code> for online services. Extra keys such as <code>"oauth"</code> are only editable here.
            </p>
          </section>
        )}
      </div>
    </div>
    </>
  );
}

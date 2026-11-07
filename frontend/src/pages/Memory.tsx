import { useEffect, useState } from "react";
import { api } from "../api";

type Key = "context" | "memory";
const TABS: { key: Key; label: string; file: string; help: string }[] = [
  { key: "context", label: "About me", file: "context.md", help: "Tell Harbor who you are and how you like to work." },
  { key: "memory", label: "What Harbor remembers", file: "memory.md", help: "Facts Harbor saved when you asked it to remember something." },
];

export default function MemoryPage() {
  const [tab, setTab] = useState<Key>("context");
  const [values, setValues] = useState<Record<Key, string> | null>(null);
  const [saved, setSaved] = useState<Record<Key, string> | null>(null);
  const [files, setFiles] = useState<{ path: string; size: number }[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<Record<Key, string>>("/memory").then((m) => { setValues(m); setSaved(m); });
    api.get<{ path: string; size: number }[]>("/files").then(setFiles);
  }, []);

  const upload = async (list: FileList | null) => {
    if (!list) return;
    setError("");
    for (const f of Array.from(list)) {
      const body = new FormData();
      body.append("file", f);
      const res = await fetch("/api/files", { method: "POST", body, credentials: "same-origin" });
      if (!res.ok) setError((await res.json().catch(() => ({}))).detail ?? "Upload failed");
    }
    api.get<{ path: string; size: number }[]>("/files").then(setFiles);
  };

  if (!values || !saved) return <div className="page" />;
  const current = TABS.find((t) => t.key === tab)!;
  const dirty = values[tab] !== saved[tab];

  const save = async () => {
    setError("");
    try {
      await api.put(`/memory/${tab}`, { content: values[tab] });
      setSaved({ ...saved, [tab]: values[tab] });
      setStatus("Saved");
      setTimeout(() => setStatus(""), 2000);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="page">
      <div className="page-inner">
        <div>
          <h1>Memory</h1>
          <p className="lead">Harbor reads these notes before every conversation. Edit them any time.</p>
        </div>
        <div className="segmented" role="tablist" aria-label="Memory files">
          {TABS.map((t) => (
            <button key={t.key} role="tab" aria-selected={tab === t.key} onClick={() => { setTab(t.key); setStatus(""); }}>
              {t.label}
            </button>
          ))}
        </div>
        <div className="stack">
          <div className="row between">
            <label htmlFor="memory-editor" className="hint"><code>{current.file}</code> · {current.help}</label>
          </div>
          <textarea id="memory-editor" className="textarea" rows={16} value={values[tab]}
            onChange={(e) => setValues({ ...values, [tab]: e.target.value })} />
          {error && <div className="banner" role="alert">{error}</div>}
          <div className="row between">
            <span className="hint" role="status">{status || (dirty ? "Unsaved changes" : "")}</span>
            <button className="btn" onClick={save} disabled={!dirty}>Save</button>
          </div>
        </div>
        <section className="stack">
          <div className="row between">
            <h2>Workspace files</h2>
            <label className="btn secondary small" style={{ cursor: "pointer" }}>
              Upload
              <input type="file" multiple className="sr-only" data-testid="upload" onChange={(e) => { upload(e.target.files); e.target.value = ""; }} />
            </label>
          </div>
          <p className="hint" style={{ margin: 0 }}>Everything Harbor creates lives in <code>/workspace</code> inside your sandbox.</p>
          <div className="list">
            {files.length === 0 && <div className="empty">No files yet.</div>}
            {files.map((f) => (
              <div className="list-item" key={f.path} style={{ padding: "10px 20px" }}>
                <code className="grow">{f.path}</code>
                <span className="sub">{f.size < 1024 ? `${f.size} B` : `${(f.size / 1024).toFixed(1)} KB`}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

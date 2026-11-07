import { useCallback, useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, uploadFile, type FileEntry } from "../api";
import { Topbar, useApp } from "../App";
import { IconFile, IconFolder, IconImage } from "../components/icons";

type Preview = { path: string; size: number; binary: boolean; truncated: boolean; content: string };
const IMAGE = /\.(png|jpe?g|gif|webp|svg)$/i;

const size = (n?: number) => (n == null ? "" : n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`);
const raw = (path: string, download = false) => `/api/files/raw?path=${encodeURIComponent(path)}${download ? "&download=true" : ""}`;

/** A read-only view of the agent's workspace. Changes happen by asking the agent; files can be uploaded. */
export default function FilesPage() {
  const [path, setPath] = useState("");
  const [entries, setEntries] = useState<FileEntry[] | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const { refresh } = useApp();

  const open = useCallback(async (dir: string) => {
    setError("");
    const r = await api.get<{ path: string; entries: FileEntry[] }>(`/files?path=${encodeURIComponent(dir)}`);
    setPath(r.path);
    setEntries(r.entries);
    setPreview(null);
  }, []);
  useEffect(() => { open(""); }, [open]);

  const show = async (e: FileEntry) => {
    if (e.type === "dir") return open(e.path);
    setPreview(await api.get<Preview>(`/files/content?path=${encodeURIComponent(e.path)}`));
  };

  const upload = async (files: FileList | null) => {
    if (!files) return;
    setError("");
    try {
      for (const f of Array.from(files)) await uploadFile("/files", f, { folder: path });
    } catch (e) {
      setError((e as Error).message);
    }
    open(path);
    refresh();
  };

  const parts = path ? path.split("/") : [];
  const name = preview?.path.split("/").pop() ?? "";

  return (
    <>
    <Topbar title="Files">
      <button className="btn primary" onClick={() => input.current?.click()}>Upload</button>
      <input ref={input} type="file" multiple className="sr-only" data-testid="upload" aria-label="Upload files"
        onChange={(e) => { upload(e.target.files); e.target.value = ""; }} />
    </Topbar>
    <div className="page">
      <div className="page-inner wide">
        <div>
          <h1>Files</h1>
          <p className="lead">Your agent's workspace. To change something, ask in chat.</p>
        </div>
        <nav className="crumbs" aria-label="Folder">
          {parts.length ? <button onClick={() => open("")}>workspace</button> : <span className="here">workspace</span>}
          {parts.map((p, i) => (
            <span key={i} className="row-flex" style={{ gap: 6 }}>
              <span>/</span>
              {i === parts.length - 1 ? <span className="here">{p}</span> : <button onClick={() => open(parts.slice(0, i + 1).join("/"))}>{p}</button>}
            </span>
          ))}
        </nav>
        {error && <div className="banner" role="alert">{error}</div>}
        <div className="browser">
          <div className="list" role="list" aria-label="Files">
            {entries?.length === 0 && <div className="empty">This folder is empty.</div>}
            {entries?.map((e) => (
              <div role="listitem" key={e.path}><button className={`entry${preview?.path === e.path ? " active" : ""}`} onClick={() => show(e)}>
                {e.type === "dir" ? <IconFolder /> : IMAGE.test(e.name) ? <IconImage /> : <IconFile />}
                <span className="name">{e.name}</span>
                <span className="meta">{e.type === "dir" ? `${e.items} item${e.items === 1 ? "" : "s"}` : size(e.size)}</span>
              </button></div>
            ))}
          </div>
          <section className="preview" aria-label="Preview">
            {preview ? (
              <>
                <div className="preview-head">
                  <span style={{ fontWeight: 600 }}>{name}</span>
                  <a href={raw(preview.path, true)}>Download</a>
                </div>
                <div className="preview-body" data-testid="preview">
                  {IMAGE.test(name) ? <img src={raw(preview.path)} alt={name} />
                    : preview.binary ? <p className="hint">This file can't be previewed. Download it to open it.</p>
                    : /\.md$/i.test(name) ? <div className="answer"><Markdown remarkPlugins={[remarkGfm]}>{preview.content}</Markdown></div>
                    : <pre className="text">{preview.content}</pre>}
                  {preview.truncated && <p className="hint">Showing the first 500 KB.</p>}
                </div>
              </>
            ) : (
              <div className="empty">Select a file to preview it.</div>
            )}
          </section>
        </div>
      </div>
    </div>
    </>
  );
}

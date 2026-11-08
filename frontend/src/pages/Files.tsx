import { useCallback, useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useNavigate } from "react-router-dom";
import { api, formatSize as size, rawUrl as raw, uploadFile, type FileEntry } from "../api";
import { PageHeader, Topbar, useApp } from "../App";
import { IconDownload, IconFile, IconFolder, IconUploadSm } from "../components/icons";

type Preview = { path: string; size: number; binary: boolean; truncated: boolean; content: string };
const IMAGE = /\.(png|jpe?g|gif|webp|svg)$/i;
/** The files the agent itself keeps, explained where people meet them. */
const ABOUT: Record<string, string> = {
  "context.md": "What your agent knows about you",
  "memory.md": "What your agent has learned while working",
  skills: "Know-how your agent can use",
  apps: "Apps your agent built for you",
};

/** A read-only view of the agent's workspace. Changes happen by asking the agent; files can be uploaded. */
export default function FilesPage() {
  const [path, setPath] = useState("");
  const [entries, setEntries] = useState<FileEntry[] | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const { refresh } = useApp();
  const navigate = useNavigate();

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
  const folders = entries?.filter((e) => e.type === "dir").length ?? 0;

  return (
    <>
    <Topbar title="Files" phoneOnly />
    <div className="page">
      <div className="page-inner wide">
        <PageHeader title="Files" lead="Your agent's workspace. To change a file, ask in chat.">
          <button className="btn primary" onClick={() => input.current?.click()}><IconUploadSm />Upload</button>
          <input ref={input} type="file" multiple className="sr-only" data-testid="upload" aria-label="Upload files" tabIndex={-1}
            onChange={(e) => { upload(e.target.files); e.target.value = ""; }} />
        </PageHeader>
        <div className="drive-bar">
          <nav className="pathbar" aria-label="Folder">
            {parts.length ? <button onClick={() => open("")}>workspace</button> : <span className="here">workspace</span>}
            {parts.map((p, i) => (
              <span key={i} className="seg-part">
                <span className="sep">/</span>
                {i === parts.length - 1 ? <span className="here">{p}</span> : <button onClick={() => open(parts.slice(0, i + 1).join("/"))}>{p}</button>}
              </span>
            ))}
          </nav>
          {entries && <span className="hint">{folders} folder{folders === 1 ? "" : "s"}, {entries.length - folders} file{entries.length - folders === 1 ? "" : "s"}</span>}
        </div>
        {error && <div className="banner" role="alert">{error}</div>}
        <div className="drive">
          <div className="list file-list">
            {entries && entries.length > 0 && <div className="list-head" aria-hidden="true"><span>Name</span><span style={{ textAlign: "right" }}>Size</span></div>}
            <div role="list" aria-label="Files">
              {entries?.length === 0 && <div className="empty">This folder is empty. Upload a file, or ask your agent to make one.</div>}
              {entries?.map((e) => {
                const about = path === "" ? ABOUT[e.name] : undefined;
                return (
                  <div role="listitem" key={e.path}>
                    <button className={`file-row ${e.type}`} onClick={() => show(e)} aria-pressed={e.type === "file" ? preview?.path === e.path : undefined}>
                      <span className="name">
                        {e.type === "dir" ? <IconFolder /> : IMAGE.test(e.name) ? <img className="row-thumb" src={raw(e.path)} alt="" loading="lazy" /> : <IconFile />}
                        <span className="text"><span>{e.name}</span>{about && <span className="desc">{about}</span>}</span>
                      </span>
                      <span className="size">{e.type === "dir" ? `${e.items} item${e.items === 1 ? "" : "s"}` : size(e.size)}</span>
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
          <section className="details" aria-label="Preview">
            {preview ? (
              <>
                <div className="details-head">
                  <span className="text"><span className="name">{name}</span>{preview.path !== name && <span className="meta mono">{preview.path}</span>}</span>
                  <a className="btn sm" href={raw(preview.path, true)}><IconDownload />Download</a>
                </div>
                <div className="preview-body" data-testid="preview">
                  {IMAGE.test(name) ? <img src={raw(preview.path)} alt={name} />
                    : preview.binary ? <p className="hint">This file can't be previewed. Download it to open it.</p>
                    : /\.md$/i.test(name) ? <div className="answer"><Markdown remarkPlugins={[remarkGfm]}>{preview.content}</Markdown></div>
                    : <pre className="text">{preview.content}</pre>}
                  {preview.truncated && <p className="hint">Showing the first 500 KB.</p>}
                </div>
                <dl className="facts"><dt>Size</dt><dd>{size(preview.size)}</dd><dt>Type</dt><dd>{ext(name) || "File"}</dd></dl>
                <div className="details-foot">
                  <button className="btn" onClick={() => navigate("/", { state: { draft: `Change ${preview.path}: ` } })}>Ask the agent to edit this</button>
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

const ext = (n: string) => (n.includes(".") ? n.split(".").pop()!.toUpperCase() : "");

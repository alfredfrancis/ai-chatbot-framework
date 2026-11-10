import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { newSession, type Attachment } from "../acp";
import { api, type ChatSummary, type FileEntry, type Project, type Task } from "../api";
import { Topbar, useApp } from "../App";
import { IconFile, IconFolder, IconPlus, IconTrash } from "../components/icons";
import { MoreMenu } from "../components/Menu";
import { Composer } from "./Chat";
import { isDone, schedule, TaskForm, when } from "./Tasks";

type Detail = { project: Project; chats: ChatSummary[]; tasks: Task[] };
type Editing = "details" | "instructions" | "folder" | "task" | null;
const FILES_SHOWN = 6;

function Section({ title, action, children, testId }: { title: string; action?: ReactNode; children: ReactNode; testId?: string }) {
  return (
    <section className="card" aria-label={title} data-testid={testId}>
      <div className="card-head"><h2>{title}</h2>{action}</div>
      {children}
    </section>
  );
}

/** One project: start a chat in it, and see its chats, instructions, folder and tasks. */
export default function ProjectPage() {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const { refresh } = useApp();
  const [data, setData] = useState<Detail | null>(null);
  const [files, setFiles] = useState<FileEntry[] | null>(null);
  const [editing, setEditing] = useState<Editing>(null);
  const [draft, setDraft] = useState({ name: "", description: "", instructions: "", folder: "" });
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const d = await api.get<Detail>(`/projects/${id}`);
      setData(d);
      setFiles(d.project.folder
        ? await api.get<{ entries: FileEntry[] }>(`/files?path=${encodeURIComponent(d.project.folder)}`).then((r) => r.entries).catch(() => [])
        : null);
    } catch {
      navigate("/projects", { replace: true });
    }
  }, [id, navigate]);
  useEffect(() => { setData(null); setEditing(null); load(); }, [load]);

  if (!data) return <Topbar crumb="Projects" crumbTo="/projects" title="" />;
  const { project: p, chats, tasks } = data;

  const edit = (what: Editing) => { setError(""); setDraft({ name: p.name, description: p.description, instructions: p.instructions, folder: p.folder }); setEditing(what); };
  const save = (fields: Partial<typeof draft>) => async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await api.patch(`/projects/${id}`, fields);
      setEditing(null);
      await load();
      refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  };
  const start = async (text: string, attached: Attachment[] = []) => {
    const s = await newSession(id);
    refresh();
    navigate(`/c/${s.sessionId}`, { state: { pending: { text, files: attached } } });
  };
  const runNow = async (t: Task) => {
    const r = await api.post<{ chat_id: number }>(`/tasks/${t.id}/run`);
    refresh();
    if (r.chat_id) navigate(`/c/${r.chat_id}`);
  };
  const remove = async () => {
    await api.del(`/projects/${id}`);
    refresh();
    navigate("/projects");
  };
  const buttons = (label: string) => (
    <>
      {error && <div className="banner" role="alert">{error}</div>}
      <div className="row-flex end">
        <button type="button" className="btn ghost sm" onClick={() => setEditing(null)}>Cancel</button>
        <button type="submit" className="btn primary sm">{label}</button>
      </div>
    </>
  );

  return (
    <>
      <Topbar crumb="Projects" crumbTo="/projects" title={p.name}>
        <MoreMenu label="Project actions" items={[
          { label: "Edit details", onSelect: () => edit("details") },
          { label: "Delete project", icon: <IconTrash />, confirm: "Yes, delete this project", onSelect: remove },
        ]} />
      </Topbar>
      <div className="page">
        <div className="page-inner wide project">
          <div className="project-main">
            {editing === "details" ? (
              <form className="card" onSubmit={save({ name: draft.name, description: draft.description })} aria-label="Project details">
                <div className="field">
                  <label htmlFor="project-name">Name</label>
                  <input id="project-name" className="input" required maxLength={200} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
                </div>
                <div className="field">
                  <label htmlFor="project-about">What is it about?</label>
                  <textarea id="project-about" className="input" rows={2} maxLength={500} value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} />
                </div>
                <span className="hint">Deleting a project keeps its chats, tasks and files.</span>
                {buttons("Save details")}
              </form>
            ) : (
              <header>
                <h1>{p.name}</h1>
                {p.description && <p className="lead">{p.description}</p>}
              </header>
            )}
            <Composer key={id} onSend={start} running={false} placeholder="Start a chat in this project" />
            <section className="stack" aria-labelledby="project-chats">
              <h2 className="subhead" id="project-chats">Chats</h2>
              <div className="list" role="list" aria-label="Chats in this project">
                {chats.length === 0 && <div className="empty">No chats yet. Whatever you start here follows this project's instructions.</div>}
                {chats.map((c) => (
                  <div role="listitem" key={c.id}>
                    <Link className="lrow" to={`/c/${c.id}`}>
                      <span className="grow">
                        <span className="title">{c.title}</span>
                        <span className="meta">{c.task_id ? "From a task · " : ""}{when(c.updated_at)}</span>
                      </span>
                    </Link>
                  </div>
                ))}
              </div>
            </section>
          </div>

          <aside className="project-side" aria-label="Project setup">
            <Section title="Instructions"
              action={editing !== "instructions" && <button className="btn ghost sm" aria-label="Edit instructions" onClick={() => edit("instructions")}>{p.instructions ? "Edit" : "Add"}</button>}>
              {editing === "instructions" ? (
                <form className="stack" onSubmit={save({ instructions: draft.instructions })}>
                  <label htmlFor="project-instructions" className="sr-only">Instructions</label>
                  <textarea id="project-instructions" className="input" rows={8} maxLength={20000} autoFocus value={draft.instructions}
                    onChange={(e) => setDraft({ ...draft, instructions: e.target.value })}
                    placeholder="How your agent should work here: the goal, the tone, what to check, what to avoid." />
                  {buttons("Save instructions")}
                </form>
              ) : p.instructions ? (
                <p className="project-text" data-testid="project-instructions">{p.instructions}</p>
              ) : (
                <p className="hint">Tell your agent how to work in this project. It follows this in every chat and task here.</p>
              )}
            </Section>

            <Section title="Folder" testId="project-folder"
              action={editing !== "folder" && <button className="btn ghost sm" aria-label={p.folder ? "Change folder" : "Attach a folder"} onClick={() => edit("folder")}>{p.folder ? "Change" : "Attach"}</button>}>
              {editing === "folder" ? (
                <form className="stack" onSubmit={save({ folder: draft.folder })}>
                  <label htmlFor="project-folder" className="sr-only">Folder</label>
                  <input id="project-folder" className="input mono" maxLength={500} autoFocus value={draft.folder}
                    onChange={(e) => setDraft({ ...draft, folder: e.target.value })} placeholder="projects/website" />
                  <span className="hint">A folder in your files. It is made if it doesn't exist; leave empty for none. Detaching never deletes files.</span>
                  {buttons("Save folder")}
                </form>
              ) : p.folder ? (
                <>
                  <span className="row-flex folder-path"><IconFolder /><span className="mono">{p.folder}</span></span>
                  {files && files.length === 0 && <p className="hint">Nothing in it yet. Files your agent makes for this project go here.</p>}
                  {files && files.length > 0 && (
                    <ul className="project-files" aria-label="Files in the folder">
                      {files.slice(0, FILES_SHOWN).map((f) => (
                        <li key={f.path}>{f.type === "dir" ? <IconFolder /> : <IconFile />}<span className="name">{f.name}</span></li>
                      ))}
                      {files.length > FILES_SHOWN && <li className="more">and {files.length - FILES_SHOWN} more</li>}
                    </ul>
                  )}
                  <Link to={`/files?path=${encodeURIComponent(p.folder)}`}>Open in Files</Link>
                </>
              ) : (
                <p className="hint">Attach a folder from your files and your agent keeps this project's work in it.</p>
              )}
            </Section>

            <Section title="Tasks"
              action={editing !== "task" && <button className="btn ghost sm" aria-label="New task" onClick={() => edit("task")}><IconPlus size={16} />New</button>}>
              {editing === "task" && <TaskForm projectId={id} onCancel={() => setEditing(null)} onDone={() => { setEditing(null); load(); refresh(); }} />}
              {tasks.length === 0 && editing !== "task" && <p className="hint">Put work in this project on a schedule. Each run is a chat here.</p>}
              {tasks.length > 0 && (
                <div className="list">
                  {tasks.map((t) => (
                    <div className="lrow" key={t.id} data-testid={`task-${t.name}`}>
                      <div className="grow">
                        <span className="title">{t.name}</span>
                        <span className="meta">{schedule(t)}{isDone(t) ? " · Done" : t.enabled ? "" : " · Paused"}</span>
                      </div>
                      <div className="side"><button className="btn sm" onClick={() => runNow(t)}>Run now</button></div>
                    </div>
                  ))}
                </div>
              )}
              {tasks.length > 0 && <Link to="/tasks">Manage in Tasks</Link>}
            </Section>
          </aside>
        </div>
      </div>
    </>
  );
}

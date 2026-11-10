import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, type Project } from "../api";
import { PageHeader, Topbar, useApp } from "../App";
import { IconPlus } from "../components/icons";

const count = (n: number, one: string) => `${n} ${one}${n === 1 ? "" : "s"}`;

function ProjectForm({ onCancel }: { onCancel: () => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const { refresh } = useApp();

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const p = await api.post<Project>("/projects", { name, description });
      refresh();
      navigate(`/projects/${p.id}`);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <form className="card" onSubmit={submit} aria-label="New project">
      <div className="field">
        <label htmlFor="project-name">Name</label>
        <input id="project-name" className="input" required maxLength={200} autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="Website relaunch" />
      </div>
      <div className="field">
        <label htmlFor="project-about">What is it about?</label>
        <textarea id="project-about" className="input" rows={2} maxLength={500} value={description} onChange={(e) => setDescription(e.target.value)}
          placeholder="What you are trying to get done, in a line or two" />
      </div>
      <span className="hint">Next you can add instructions for your agent and attach a folder of files.</span>
      {error && <div className="banner" role="alert">{error}</div>}
      <div className="row-flex end">
        <button type="button" className="btn ghost" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn primary">Create project</button>
      </div>
    </form>
  );
}

/** Every project as a card; a project opens on its own page (pages/Project.tsx). */
export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [params, setParams] = useSearchParams();
  const [creating, setCreating] = useState(params.get("new") === "1");
  useEffect(() => { api.get<Project[]>("/projects").then(setProjects).catch(() => setProjects([])); }, []);
  useEffect(() => { if (params.get("new") === "1") { setCreating(true); setParams({}, { replace: true }); } }, [params, setParams]);

  return (
    <>
      <Topbar title="Projects" phoneOnly />
      <div className="page">
        <div className="page-inner wide">
          <PageHeader title="Projects" lead="Ongoing work with its own instructions, files, chats and tasks.">
            {!creating && !!projects?.length && <button className="btn primary" onClick={() => setCreating(true)}><IconPlus />New project</button>}
          </PageHeader>
          {creating && <ProjectForm onCancel={() => setCreating(false)} />}
          {projects?.length === 0 && !creating && (
            <section className="empty-state" aria-labelledby="no-projects">
              <div>
                <h2 id="no-projects">Keep ongoing work in one place</h2>
                <p>A project tells your agent how to work on one thing: instructions it follows in every chat there, a folder for the files, and tasks that run on a schedule.</p>
              </div>
              <button className="btn primary" onClick={() => setCreating(true)}><IconPlus />New project</button>
            </section>
          )}
          {!!projects?.length && (
            <div className="project-grid">
              {projects.map((p) => (
                <Link key={p.id} to={`/projects/${p.id}`} className="project-card">
                  <span className="title">{p.name}</span>
                  <span className="about">{p.description || (p.instructions ? "Has instructions for your agent." : "No description yet.")}</span>
                  <span className="meta">
                    {count(p.chats, "chat")}{p.tasks > 0 && ` · ${count(p.tasks, "task")}`}{p.folder && ` · ${p.folder}`}
                  </span>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

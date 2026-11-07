import { useEffect, useRef, useState, type DragEvent } from "react";
import { api, uploadFile, type Skill } from "../api";
import { Topbar, useApp } from "../App";
import { IconUpload } from "../components/icons";

export default function SkillsPage() {
  const { refresh } = useApp();
  const [skills, setSkills] = useState<Skill[] | null>(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [over, setOver] = useState(false);
  const [confirm, setConfirm] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const load = () => api.get<Skill[]>("/skills").then(setSkills);
  useEffect(() => { load(); }, []);

  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    setError("");
    setMsg("");
    try {
      for (const f of Array.from(files)) {
        const s = await uploadFile("/skills", f);
        setMsg(`Added “${s.name}”.`);
      }
    } catch (e) {
      setError((e as Error).message);
    }
    load();
    refresh();
  };
  const remove = async (s: Skill) => {
    if (confirm !== s.name) { setConfirm(s.name); return; }
    await api.del(`/skills/${s.name}`);
    setConfirm(null);
    load();
    refresh();
  };
  const onDrop = (e: DragEvent) => { e.preventDefault(); setOver(false); upload(e.dataTransfer.files); };

  return (
    <>
      <Topbar title="Skills">
        <button className="btn primary" onClick={() => input.current?.click()}>Upload skill</button>
      </Topbar>
      <div className="page">
        <div className="page-inner">
          <div>
            <h1>Skills</h1>
            <p className="lead">Know-how your agent loads when a job needs it. Upload a skill, or ask the agent to write one.</p>
          </div>
          <label className={`dropzone${over ? " over" : ""}`} onDragOver={(e) => { e.preventDefault(); setOver(true); }}
            onDragLeave={() => setOver(false)} onDrop={onDrop}>
            <IconUpload />
            <span style={{ fontWeight: 550 }}>Drop a skill here, or click to choose a file</span>
            <span className="hint">A .zip with a SKILL.md inside, or a single SKILL.md</span>
            <input ref={input} type="file" accept=".zip,.skill,.md" className="sr-only" data-testid="skill-upload"
              onChange={(e) => { upload(e.target.files); e.target.value = ""; }} />
          </label>
          {error && <div className="banner" role="alert">{error}</div>}
          {msg && <div className="hint" role="status">{msg}</div>}
          {skills && (
            <div className="list">
              <div className="list-head"><span style={{ flex: 1 }}>Skill</span><span>Files</span></div>
              {skills.map((s) => (
                <div className="lrow" key={s.name} data-testid={`skill-${s.name}`}>
                  <div className="tile" aria-hidden="true">{s.name[0]}</div>
                  <div className="grow">
                    <span className="title">{s.name}</span>
                    <span className="meta">{s.description}</span>
                  </div>
                  <div className="side">
                    <span className="badge plain">{s.files} file{s.files === 1 ? "" : "s"}</span>
                    <button className={`btn ${confirm === s.name ? "danger" : "ghost"} sm`} onClick={() => remove(s)}
                      aria-label={confirm === s.name ? `Confirm remove ${s.name}` : `Remove ${s.name}`}>
                      {confirm === s.name ? "Remove?" : "Remove"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
          <p className="hint">
            Skills use the open Agent Skills format: a folder with a <code>SKILL.md</code> (a name and a description at the top,
            then instructions) plus any scripts it needs. The agent sees only the name and description until a job needs the skill.
          </p>
        </div>
      </div>
    </>
  );
}

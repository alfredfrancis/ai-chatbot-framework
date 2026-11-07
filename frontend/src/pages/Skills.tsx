import { useEffect, useRef, useState, type DragEvent } from "react";
import { Link } from "react-router-dom";
import { api, uploadFile, type Skill } from "../api";
import { IconUpload } from "../components/icons";

const TINTS = [["var(--signal-soft)", "var(--signal-text)"], ["#EEF0FF", "#3B4BC8"], ["#FDF1E7", "#A04A00"], ["#F2EEFC", "#5B32B4"]];
function tint(name: string) {
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return TINTS[h % TINTS.length];
}

export default function SkillsPage() {
  const [skills, setSkills] = useState<Skill[] | null>(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [over, setOver] = useState(false);
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
  };
  const remove = async (s: Skill) => {
    if (!confirm(`Remove the “${s.name}” skill?`)) return;
    await api.del(`/skills/${s.name}`);
    load();
  };
  const onDrop = (e: DragEvent) => { e.preventDefault(); setOver(false); upload(e.dataTransfer.files); };

  return (
    <div className="page">
      <div className="page-inner">
        <div>
          <h1>Skills</h1>
          <p className="lead">Know-how your agent loads when a job needs it. Upload a skill, or ask the agent to write one.</p>
        </div>
        <label className={`dropzone${over ? " over" : ""}`} onDragOver={(e) => { e.preventDefault(); setOver(true); }}
          onDragLeave={() => setOver(false)} onDrop={onDrop}>
          <span style={{ color: "var(--signal-text)" }}><IconUpload /></span>
          <span className="title">Drop a skill here, or click to upload</span>
          <span className="hint">A .zip with a SKILL.md inside, or a single SKILL.md</span>
          <input ref={input} type="file" accept=".zip,.skill,.md" className="sr-only" data-testid="skill-upload"
            onChange={(e) => { upload(e.target.files); e.target.value = ""; }} />
        </label>
        {error && <div className="banner" role="alert">{error}</div>}
        {msg && <div className="hint" role="status">{msg}</div>}
        <div className="skill-grid">
          {skills?.map((s) => {
            const [bg, fg] = tint(s.name);
            return (
              <div className="skill" key={s.name} data-testid={`skill-${s.name}`}>
                <div className="row">
                  <div className="avatar" style={{ background: bg, color: fg, width: 32, height: 32, borderRadius: 9 }} aria-hidden="true">{s.name[0]}</div>
                  <span className="title">{s.name}</span>
                  <span style={{ marginLeft: "auto" }} className="hint">{s.files} file{s.files === 1 ? "" : "s"}</span>
                </div>
                <p>{s.description}</p>
                <div className="row between">
                  <Link to="/files" className="hint">{s.path}</Link>
                  <button className="btn danger small" onClick={() => remove(s)} aria-label={`Remove ${s.name}`}>Remove</button>
                </div>
              </div>
            );
          })}
        </div>
        <p className="hint">
          Skills follow the open Agent Skills format: a folder with a <code>SKILL.md</code> (a name and a description in its
          header, then instructions) plus any scripts it needs. Only the name and description are shown to the agent until a
          task needs the skill.
        </p>
      </div>
    </div>
  );
}

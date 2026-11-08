import { useEffect, useRef, useState, type DragEvent } from "react";
import { api, uploadFile, type Skill } from "../api";
import { PageHeader, Topbar, useApp } from "../App";
import { IconUploadSm } from "../components/icons";
import { MoreMenu } from "../components/Menu";

const SPELLING: Record<string, string> = { openui: "OpenUI", pdf: "PDF", csv: "CSV", api: "API", ai: "AI", mcp: "MCP", ui: "UI" };

/** "action-items" → "Action items", "pdf" → "PDF": skill names are ids; people read words. */
export const readable = (name: string) => {
  const words = name.split(/[-_]+/).filter(Boolean).map((w) => SPELLING[w] ?? w);
  if (!words.length) return name;
  const first = SPELLING[name.split(/[-_]+/)[0]] ? words[0] : words[0][0].toUpperCase() + words[0].slice(1);
  return [first, ...words.slice(1)].join(" ");
};

function SkillRow({ s, onRemove }: { s: Skill; onRemove: (s: Skill) => Promise<void> }) {
  return (
    <div className="lrow" data-testid={`skill-${s.name}`}>
      <div className={`tile${s.builtin ? " builtin" : ""}`} aria-hidden="true">{s.name[0]}</div>
      <div className="grow">
        <span className="title" title={s.name}>{readable(s.name)}</span>
        <span className="meta">{s.description}</span>
      </div>
      <div className="side">
        <span className="badge plain">{s.files} file{s.files === 1 ? "" : "s"}</span>
        <MoreMenu label={`More actions for ${s.name}`}
          items={[{ label: "Remove skill", confirm: "Yes, remove this skill", onSelect: () => onRemove(s) }]} />
      </div>
    </div>
  );
}

export default function SkillsPage() {
  const { refresh } = useApp();
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
    refresh();
  };
  const remove = async (s: Skill) => {
    await api.del(`/skills/${s.name}`);
    load();
    refresh();
  };
  // The whole page takes a dropped skill; the overlay says so while a file is over it.
  const files = (e: DragEvent) => e.dataTransfer.types.includes("Files");
  const onDragOver = (e: DragEvent) => { if (!files(e)) return; e.preventDefault(); setOver(true); };
  const onDragLeave = (e: DragEvent) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setOver(false); };
  const onDrop = (e: DragEvent) => { if (!files(e)) return; e.preventDefault(); setOver(false); upload(e.dataTransfer.files); };

  const mine = skills?.filter((s) => !s.builtin) ?? [];
  const builtin = skills?.filter((s) => s.builtin) ?? [];

  return (
    <>
      <Topbar title="Skills" phoneOnly />
      <div className={`page${over ? " dropping" : ""}`} onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop} data-testid="skills-page">
        <div className="page-inner">
          <PageHeader title="Skills" lead="Know-how your agent picks up when a job needs it. Drop a skill anywhere here to add it.">
            <button className="btn primary" onClick={() => input.current?.click()}><IconUploadSm />Upload skill</button>
            <input ref={input} type="file" accept=".zip,.skill,.md" className="sr-only" data-testid="skill-upload" aria-label="Upload a skill"
              tabIndex={-1} onChange={(e) => { upload(e.target.files); e.target.value = ""; }} />
          </PageHeader>
          {error && <div className="banner" role="alert">{error}</div>}
          {msg && <div className="hint" role="status">{msg}</div>}
          {skills && (
            <>
              <section className="stack" aria-labelledby="my-skills">
                <h2 className="subhead" id="my-skills">Yours · {mine.length}</h2>
                <div className="list skill-list">
                  {mine.length === 0
                    ? <div className="empty">Skills you upload, or ask the agent to write, show up here.</div>
                    : mine.map((s) => <SkillRow key={s.name} s={s} onRemove={remove} />)}
                </div>
              </section>
              {builtin.length > 0 && (
                <section className="stack" aria-labelledby="builtin-skills">
                  <div className="row-flex between wrap">
                    <h2 className="subhead" id="builtin-skills">Built in · {builtin.length}</h2>
                    <span className="hint">Included with every account. You can change or remove them.</span>
                  </div>
                  <div className="list skill-list">{builtin.map((s) => <SkillRow key={s.name} s={s} onRemove={remove} />)}</div>
                </section>
              )}
            </>
          )}
          <p className="hint">
            A skill is a <code>.zip</code> with a <code>SKILL.md</code> inside (a name and a description at the top, then instructions) plus any
            scripts it needs, or a single <code>SKILL.md</code>. The agent sees only the name and description until a job needs the skill.
          </p>
        </div>
      </div>
    </>
  );
}

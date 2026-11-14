import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, type Settings, type Task } from "../api";
import { PageHeader, Topbar, useApp } from "../App";
import { IconPlus } from "../components/icons";
import { MoreMenu } from "../components/Menu";
import { Toggle } from "../components/Toggle";

type Freq = "once" | "hourly" | "daily" | "weekdays" | "weekly" | "custom";
const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const localTz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";

export function toCron(freq: Freq, time: string, day: number, custom: string): string {
  const [h, m] = time.split(":").map((x) => String(Number(x)));
  switch (freq) {
    case "hourly": return `${m} * * * *`;
    case "daily": return `${m} ${h} * * *`;
    case "weekdays": return `${m} ${h} * * 1-5`;
    case "weekly": return `${m} ${h} * * ${day}`;
    default: return custom.trim();
  }
}

export function describe(cron: string): string {
  const p = cron.trim().split(/\s+/);
  if (p.length !== 5) return cron;
  const [m, h, dom, mon, dow] = p;
  const num = (x: string) => /^\d+$/.test(x);
  const at = num(h) && num(m) ? `${h.padStart(2, "0")}:${m.padStart(2, "0")}` : "";
  if (dom !== "*" || mon !== "*") return `Custom (${cron})`;
  if (num(m) && h === "*" && dow === "*") return m === "0" ? "Every hour" : `Every hour at :${m.padStart(2, "0")}`;
  if (!at) return `Custom (${cron})`;
  if (dow === "*") return `Every day at ${at}`;
  if (dow === "1-5") return `Every weekday at ${at}`;
  if (num(dow) && Number(dow) < 7) return `Every ${DAYS[Number(dow)]} at ${at}`;
  return `Custom (${cron})`;
}

/** A one-off task whose run has started: it is done and won't run again unless given a new time. */
export const isDone = (t: Task) => !!t.run_at && !t.enabled && !!t.last_run_at;

export function schedule(t: Task): string {
  if (!t.run_at) return describe(t.schedule);
  const d = new Date(t.run_at);
  return `Once on ${d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}`;
}

/** Tomorrow at 09:00 local time, as a datetime-local value. */
function tomorrowAt9(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T09:00`;
}

export function when(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const diff = d.getTime() - Date.now();
  const fmt = d.toLocaleString(undefined, { weekday: "short", hour: "2-digit", minute: "2-digit", month: "short", day: "numeric" });
  if (Math.abs(diff) < 60_000) return "just now";
  return fmt;
}

/** The models a task can run on: the user's default ("") and every model that is on, with their names. */
function useTaskModels() {
  const [s, setS] = useState<Settings | null>(null);
  useEffect(() => { api.get<Settings>("/settings").then(setS).catch(() => setS(null)); }, []);
  const def = s ? s.model || s.defaults.model : "";
  const nameOf = (key: string) => s?.models.find((m) => m.key === key)?.name || key.split(":").slice(1).join(":") || key;
  const options = s ? s.models.filter((m) => m.enabled && m.key !== def) : [];
  return { ready: !!s, defaultName: def ? nameOf(def) : "", options, nameOf };
}

type Template = { name: string; prompt: string; freq: Freq; time: string; day: number; blurb: string; when: string };

/** Starting points on the empty Tasks page: each opens the form filled in, to change before saving. */
const TEMPLATES: Template[] = [
  { name: "Plan my day", freq: "weekdays", time: "08:00", day: 1, when: "Weekdays · 08:00",
    blurb: "A short plan for the day from your notes and files.",
    prompt: "Look at my notes and files and write a short plan for today: the three things that matter most, then the rest. Save it to notes/today.md." },
  { name: "Weekly review", freq: "weekly", time: "16:00", day: 5, when: "Fridays · 16:00",
    blurb: "What changed this week, what's done and what's next.",
    prompt: "Review what changed in my files this week. Write what got done, what is still open and what's next. Save it to notes/weekly-review.md." },
  { name: "Watch a web page", freq: "hourly", time: "00:00", day: 1, when: "Every hour",
    blurb: "Tells you when a price or a page you care about changes.",
    prompt: "Check https://example.com and tell me if anything important changed since the last check. Replace the address with the page to watch." },
];

/** The new-task form. With `projectId` the task belongs to that project: its runs are chats in it. */
export function TaskForm({ initial, projectId, onDone, onCancel }: { initial?: Template; projectId?: number; onDone: () => void; onCancel: () => void }) {
  const [name, setName] = useState(initial?.name ?? "");
  const [prompt, setPrompt] = useState(initial?.prompt ?? "");
  const [freq, setFreq] = useState<Freq>(initial?.freq ?? "daily");
  const [time, setTime] = useState(initial?.time ?? "08:00");
  const [day, setDay] = useState(initial?.day ?? 1);
  const [custom, setCustom] = useState("0 9 * * *");
  const [runAt, setRunAt] = useState(tomorrowAt9);
  const [model, setModel] = useState("");
  const [error, setError] = useState("");
  const models = useTaskModels();

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const timing = freq === "once" ? { run_at: runAt } : { schedule: toCron(freq, time, day, custom) };
      await api.post("/tasks", { name, prompt, ...timing, timezone: localTz, project_id: projectId ?? null, model });
      onDone();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <form className="card" onSubmit={submit} aria-label="New task">
      <div className="field">
        <label htmlFor="task-name">Name</label>
        <input id="task-name" className="input" required value={name} onChange={(e) => setName(e.target.value)} placeholder="Morning briefing" />
      </div>
      <div className="field">
        <label htmlFor="task-prompt">What should the agent do?</label>
        <textarea id="task-prompt" className="input" rows={3} required value={prompt} onChange={(e) => setPrompt(e.target.value)}
          placeholder="Check the weather in Lisbon and write a short summary to notes/today.md" />
      </div>
      <div className="grid-2">
        <div className="field">
          <label htmlFor="task-freq">Repeat</label>
          <select id="task-freq" className="input" value={freq} onChange={(e) => setFreq(e.target.value as Freq)}>
            <option value="once">Once</option>
            <option value="hourly">Every hour</option>
            <option value="daily">Every day</option>
            <option value="weekdays">Every weekday</option>
            <option value="weekly">Every week</option>
            <option value="custom">Custom (cron)</option>
          </select>
        </div>
        {freq === "once" ? (
          <div className="field">
            <label htmlFor="task-run-at">On</label>
            <input id="task-run-at" className="input" type="datetime-local" required value={runAt} onChange={(e) => setRunAt(e.target.value)} />
          </div>
        ) : freq === "custom" ? (
          <div className="field">
            <label htmlFor="task-cron">Cron expression</label>
            <input id="task-cron" className="input mono" value={custom} onChange={(e) => setCustom(e.target.value)}  />
          </div>
        ) : freq === "hourly" ? (
          <div className="field">
            <label htmlFor="task-minute">At minute</label>
            <input id="task-minute" className="input" type="number" min={0} max={59} value={Number(time.split(":")[1])}
              onChange={(e) => setTime(`00:${String(Math.min(59, Math.max(0, Number(e.target.value)))).padStart(2, "0")}`)} />
          </div>
        ) : (
          <div className="field">
            <label htmlFor="task-time">At</label>
            <input id="task-time" className="input" type="time" required value={time} onChange={(e) => setTime(e.target.value)} />
          </div>
        )}
        {freq === "weekly" && (
          <div className="field">
            <label htmlFor="task-day">On</label>
            <select id="task-day" className="input" value={day} onChange={(e) => setDay(Number(e.target.value))}>
              {DAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
            </select>
          </div>
        )}
      </div>
      <div className="field">
        <label htmlFor="task-model">Model</label>
        <select id="task-model" className="input" value={model} onChange={(e) => setModel(e.target.value)} disabled={!models.ready}>
          <option value="">Default ({models.defaultName || "your default model"})</option>
          {models.options.map((m) => <option key={m.key} value={m.key}>{m.name}</option>)}
        </select>
        <span className="hint">A small or local model is enough for many background jobs, and costs less.</span>
      </div>
      <span className="hint">Times are in your time zone ({localTz}). Each run appears as a new chat{projectId ? " in this project" : ""}.</span>
      {error && <div className="banner" role="alert">{error}</div>}
      <div className="row-flex end">
        <button type="button" className="btn ghost" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn primary">Create task</button>
      </div>
    </form>
  );
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [params, setParams] = useSearchParams();
  const [creating, setCreating] = useState(params.get("new") === "1");
  const [template, setTemplate] = useState<Template | undefined>(undefined);
  const create = (t?: Template) => { setTemplate(t); setCreating(true); };
  const navigate = useNavigate();
  const { refresh, projects } = useApp();
  const projectOf = (t: Task) => projects.find((p) => p.id === t.project_id);
  const models = useTaskModels();

  const load = () => api.get<Task[]>("/tasks").then(setTasks);
  useEffect(() => { load(); }, []);
  useEffect(() => { if (params.get("new") === "1") { setCreating(true); setParams({}, { replace: true }); } }, [params, setParams]);

  const toggle = async (t: Task, enabled: boolean) => {
    await api.patch(`/tasks/${t.id}`, { enabled });
    load();
  };
  const runNow = async (t: Task) => {
    const r = await api.post<{ chat_id: number }>(`/tasks/${t.id}/run`);
    refresh();
    if (r.chat_id) navigate(`/c/${r.chat_id}`);
  };
  const remove = async (t: Task) => {
    await api.del(`/tasks/${t.id}`);
    load();
    refresh();
  };
  const badge = (t: Task) =>
    t.last_status === "running" ? <span className="badge warning">Running</span>
      : isDone(t) ? <span className="badge">{t.last_status === "error" ? "Failed" : "Done"}</span>
      : !t.enabled ? <span className="badge">Paused</span>
      : t.last_status === "error" ? <span className="badge danger">Failed</span>
      : t.last_status === "running" ? <span className="badge warning">Running</span>
      : null; // on and nothing to report: the switch beside it already says so

  return (
    <>
      <Topbar title="Tasks" phoneOnly />
      <div className="page">
        <div className="page-inner">
          <PageHeader title="Tasks" lead="Work your agent does on a schedule. Each run opens as a chat you can read later.">
            {!creating && !!tasks?.length && <button className="btn primary" onClick={() => create()}><IconPlus />New task</button>}
          </PageHeader>
          {creating && <TaskForm key={template?.name ?? ""} initial={template} onCancel={() => setCreating(false)}
            onDone={() => { setCreating(false); load(); refresh(); }} />}
          {tasks && tasks.length === 0 && !creating && (
            <>
              <section className="empty-state" aria-labelledby="no-tasks">
                <div>
                  <h2 id="no-tasks">Put your agent on a schedule</h2>
                  <p>Say what to do and when, in plain words. The agent runs it on its own computer and leaves the result in Chats.</p>
                </div>
                <button className="btn primary" onClick={() => create()}><IconPlus />New task</button>
              </section>
              <section className="stack" aria-labelledby="task-templates">
                <h2 className="subhead" id="task-templates">Or start from one of these</h2>
                <div className="list">
                  {TEMPLATES.map((t) => (
                    <div className="lrow" key={t.name}>
                      <div className="grow"><span className="title">{t.name}</span><span className="meta">{t.blurb}</span></div>
                      <div className="side">
                        <span className="when">{t.when}</span>
                        <button className="btn sm" onClick={() => create(t)} aria-label={`Use template: ${t.name}`}>Use</button>
                      </div>
                    </div>
                  ))}
                </div>
                <p className="hint">A template fills in the form; change anything before you save.</p>
              </section>
            </>
          )}
          {tasks && tasks.length > 0 && (
            <div className="list">
              <div className="list-head"><span style={{ flex: 1 }}>Task</span><span>Status</span></div>
              {tasks.map((t) => (
                <div className="lrow" key={t.id} data-testid={`task-${t.name}`}>
                  <div className="grow">
                    <span className="title">{t.name}</span>
                    <span className="meta">
                      {projectOf(t) && <><Link to={`/projects/${t.project_id}`}>{projectOf(t)!.name}</Link> · </>}
                      {schedule(t)}
                      {t.model && ` · ${models.nameOf(t.model)}`}
                      {t.enabled ? (t.next_run_at ? ` · Next ${when(t.next_run_at)}` : "") : isDone(t) ? "" : " · Paused"}
                    </span>
                    {t.last_run_at && (
                      <span className="meta">
                        Last run {when(t.last_run_at)}
                        {t.last_chat_id && <> · <Link to={`/c/${t.last_chat_id}`}>View result</Link></>}
                      </span>
                    )}
                  </div>
                  <div className="side">
                    {badge(t)}
                    <button className="btn sm" onClick={() => runNow(t)}>Run now</button>
                    {!isDone(t) && <Toggle checked={t.enabled} onChange={(v) => toggle(t, v)} label={`${t.name} enabled`} />}
                    <MoreMenu label={`More actions for ${t.name}`}
                      items={[{ label: "Delete task", confirm: "Yes, delete this task", onSelect: () => remove(t) }]} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

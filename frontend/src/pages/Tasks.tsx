import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, type Task } from "../api";
import { Topbar, useApp } from "../App";

type Freq = "hourly" | "daily" | "weekdays" | "weekly" | "custom";
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

function when(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const diff = d.getTime() - Date.now();
  const fmt = d.toLocaleString(undefined, { weekday: "short", hour: "2-digit", minute: "2-digit", month: "short", day: "numeric" });
  if (Math.abs(diff) < 60_000) return "just now";
  return fmt;
}

function TaskForm({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const [name, setName] = useState("");
  const [prompt, setPrompt] = useState("");
  const [freq, setFreq] = useState<Freq>("daily");
  const [time, setTime] = useState("08:00");
  const [day, setDay] = useState(1);
  const [custom, setCustom] = useState("0 9 * * *");
  const [error, setError] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await api.post("/tasks", { name, prompt, schedule: toCron(freq, time, day, custom), timezone: localTz });
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
            <option value="hourly">Every hour</option>
            <option value="daily">Every day</option>
            <option value="weekdays">Every weekday</option>
            <option value="weekly">Every week</option>
            <option value="custom">Custom (cron)</option>
          </select>
        </div>
        {freq === "custom" ? (
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
      <span className="hint">Times are in your time zone ({localTz}). Each run appears as a new chat.</span>
      {error && <div className="banner" role="alert">{error}</div>}
      <div className="row-flex end">
        <button type="button" className="btn ghost" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn primary">Create task</button>
      </div>
    </form>
  );
}

function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <span className="switch">
      <input type="checkbox" role="switch" aria-label={label} checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="track" />
    </span>
  );
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [params, setParams] = useSearchParams();
  const [creating, setCreating] = useState(params.get("new") === "1");
  const [confirm, setConfirm] = useState<number | null>(null);
  const navigate = useNavigate();
  const { refresh } = useApp();

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
    if (confirm !== t.id) { setConfirm(t.id); return; }
    await api.del(`/tasks/${t.id}`);
    setConfirm(null);
    load();
    refresh();
  };
  const badge = (t: Task) =>
    !t.enabled ? <span className="badge">Paused</span>
      : t.last_status === "error" ? <span className="badge danger">Failed</span>
      : t.last_status === "running" ? <span className="badge warning">Running</span>
      : <span className="badge success">On</span>;

  return (
    <>
      <Topbar title="Tasks">
        {!creating && <button className="btn primary" onClick={() => setCreating(true)}>New task</button>}
      </Topbar>
      <div className="page">
        <div className="page-inner">
          <div>
            <h1>Tasks</h1>
            <p className="lead">Jobs your agent runs on a schedule. Each run opens as a chat.</p>
          </div>
          {creating && <TaskForm onCancel={() => setCreating(false)} onDone={() => { setCreating(false); load(); refresh(); }} />}
          {tasks && tasks.length === 0 && !creating && (
            <div className="list"><div className="empty">No tasks yet. Create one to have the agent check, summarise or tidy things up for you regularly.</div></div>
          )}
          {tasks && tasks.length > 0 && (
            <div className="list">
              <div className="list-head"><span style={{ flex: 1 }}>Task</span><span>Status</span></div>
              {tasks.map((t) => (
                <div className="lrow" key={t.id} data-testid={`task-${t.name}`}>
                  <div className="grow">
                    <span className="title">{t.name}</span>
                    <span className="meta">
                      {describe(t.schedule)}
                      {t.enabled ? (t.next_run_at ? ` · Next ${when(t.next_run_at)}` : "") : " · Paused"}
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
                    <Toggle checked={t.enabled} onChange={(v) => toggle(t, v)} label={`${t.name} enabled`} />
                    <button className={`btn ${confirm === t.id ? "danger" : "ghost"} sm`} onClick={() => remove(t)}
                      aria-label={confirm === t.id ? `Confirm delete ${t.name}` : `Delete ${t.name}`}>{confirm === t.id ? "Delete?" : "Delete"}</button>
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

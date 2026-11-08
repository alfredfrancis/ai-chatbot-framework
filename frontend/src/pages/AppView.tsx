import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import Markdown from "react-markdown";
import { Link, useParams } from "react-router-dom";
import remarkGfm from "remark-gfm";
import { api, type AppAction, type AppBlock, type AppButton, type AppDetail, type BoardItem } from "../api";
import { Topbar, useApp } from "../App";

type Act = (action: AppAction, args: Record<string, unknown>) => Promise<boolean>;

/** A personal app: blocks the agent laid out in apps/<id>/app.json, over files in the workspace. */
export default function AppPage() {
  const { id = "" } = useParams();
  const { refresh } = useApp();
  const [app, setApp] = useState<AppDetail | null>(null);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState("");
  const [output, setOutput] = useState("");
  const busy = useRef(0); // writes in flight: polls would show the file from before them
  const writes = useRef(0); // a poll that started before the latest write shows stale files

  const load = useCallback(async () => {
    if (busy.current) return;
    const seen = writes.current;
    try {
      const a = await api.get<AppDetail>(`/apps/${id}`);
      if (!busy.current && seen === writes.current) { setApp(a); setMissing(false); }
    } catch {
      setMissing(true);
    }
  }, [id]);

  useEffect(() => { setApp(null); setError(""); setOutput(""); load(); }, [load]);
  // The agent changes the files in the background: keep the screen current.
  const running = app?.running ?? false;
  const wasRunning = useRef(false);
  useEffect(() => {
    const t = setInterval(() => { if (document.visibilityState === "visible") load(); }, running ? 1000 : 4000);
    if (wasRunning.current && !running) refresh();
    wasRunning.current = running;
    return () => clearInterval(t);
  }, [load, running, refresh]);

  const act: Act = async (action, args) => {
    setError("");
    busy.current++;
    writes.current++;
    try {
      const r = await api.post<{ output?: string; chat_id?: number }>(`/apps/${id}/actions`, { action, args });
      if (r.output !== undefined) setOutput(r.output);
      if (action === "ask_agent") { setApp((a) => a && { ...a, running: true, chat_id: r.chat_id ?? a.chat_id }); refresh(); }
      return true;
    } catch (e) {
      setError((e as Error).message);
      return false;
    } finally {
      busy.current--;
      load();
    }
  };

  if (missing) {
    return (
      <>
        <Topbar crumb="Apps" title={id} />
        <div className="page"><div className="page-inner"><div className="empty">This app doesn’t exist any more. Ask the agent to make it again.</div></div></div>
      </>
    );
  }
  if (!app) return <Topbar crumb="Apps" title={id} />;

  return (
    <>
      <Topbar crumb="Apps" title={app.title}>
        {app.running && <span className="app-working" role="status"><span className="live-dot" aria-hidden="true" />Agent working…</span>}
        {app.chat_id && <Link className="btn ghost sm" to={`/c/${app.chat_id}`}>Open chat</Link>}
      </Topbar>
      <div className="page">
        <div className="page-inner wide app-page">
          <div>
            <h1>{app.title}</h1>
            {app.description && <p className="lead">{app.description}</p>}
          </div>
          {app.error && <div className="banner" role="alert">{app.error} Ask the agent to fix it.</div>}
          {error && <div className="banner" role="alert">{error}</div>}
          {app.blocks.map((b, i) => <BlockView key={`${id}-${i}`} block={b} act={act} />)}
          {output && (
            <section className="card" aria-label="Result">
              <div className="row-flex between"><h2>Result</h2><button className="btn ghost sm" onClick={() => setOutput("")}>Clear</button></div>
              <pre className="app-output">{output}</pre>
            </section>
          )}
        </div>
      </div>
    </>
  );
}

function BlockView({ block, act }: { block: AppBlock; act: Act }) {
  if (block.type === "markdown") {
    return (
      <section className="card" aria-label={block.title || "Notes"}>
        {block.title && <h2>{block.title}</h2>}
        {block.text.trim() ? <div className="answer"><Markdown remarkPlugins={[remarkGfm]}>{block.text}</Markdown></div>
          : <p className="hint">Nothing here yet.</p>}
      </section>
    );
  }
  if (block.type === "board") return <Board block={block} act={act} />;
  return <Buttons buttons={block.buttons} title={block.title} act={act} />;
}

function Buttons({ buttons, title, act }: { buttons: AppButton[]; title: string; act: Act }) {
  const [asking, setAsking] = useState<AppButton | null>(null);
  const press = (b: AppButton) => { if (b.confirm) setAsking(b); else act(b.action, b.args); };
  return (
    <section className="app-buttons" aria-label={title || "Actions"}>
      {asking ? (
        <div className="row-flex wrap" role="alertdialog" aria-label={asking.label}>
          <span>{asking.confirm}</span>
          <button className="btn primary sm" onClick={() => { setAsking(null); act(asking.action, asking.args); }}>Yes, {asking.label.toLowerCase()}</button>
          <button className="btn ghost sm" onClick={() => setAsking(null)}>Cancel</button>
        </div>
      ) : (
        <div className="row-flex wrap">
          {buttons.map((b) => <button key={b.label} className="btn" onClick={() => press(b)}>{b.label}</button>)}
        </div>
      )}
    </section>
  );
}

function Board({ block, act }: { block: AppBlock; act: Act }) {
  const [items, setItems] = useState<BoardItem[]>(block.data?.items ?? []);
  const [over, setOver] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const pending = useRef(0);
  const queue = useRef<Promise<unknown>>(Promise.resolve()); // one write at a time, in order
  useEffect(() => { if (pending.current === 0) setItems(block.data?.items ?? []); }, [block.data]);

  const columns = block.columns.length ? block.columns : [{ id: "todo", title: "To-do", hint: "" }];
  const known = new Set(columns.map((c) => c.id));
  const colOf = (it: BoardItem) => (known.has(it.column) ? it.column : columns[0].id);
  const titleOf = (col: string) => columns.find((c) => c.id === col)?.title ?? col;

  const save = (next: BoardItem[], event: string) => {
    setItems(next);
    pending.current++;
    const content = JSON.stringify({ ...block.data, items: next }, null, 2) + "\n";
    queue.current = queue.current.then(async () => {
      const ok = await act("update_file", { path: block.file, content });
      pending.current--;
      if (ok && block.on_change) await act("ask_agent", { prompt: block.on_change, event });
    });
  };
  const move = (itemId: string, to: string) => {
    const it = items.find((x) => x.id === itemId);
    if (!it || colOf(it) === to) return;
    save(items.map((x) => (x.id === itemId ? { ...x, column: to } : x)), `Moved "${it.title}" from "${titleOf(colOf(it))}" to "${titleOf(to)}" in ${block.title || "the board"}.`);
  };
  const toggle = (it: BoardItem) =>
    save(items.map((x) => (x.id === it.id ? { ...x, done: !x.done } : x)), `Marked "${it.title}" as ${it.done ? "not done" : "done"}.`);
  const add = (e: FormEvent, col: string) => {
    e.preventDefault();
    const title = (drafts[col] ?? "").trim();
    if (!title) return;
    setDrafts((d) => ({ ...d, [col]: "" }));
    const item = { id: `u${Date.now().toString(36)}`, title, column: col, done: false };
    save([...items, item], `Added "${title}" to "${titleOf(col)}".`);
  };

  return (
    <section className="stack" aria-label={block.title || "Board"}>
      {block.title && <h2>{block.title}</h2>}
      <div className={`board${columns.length === 4 ? " matrix" : ""}`}>
        {columns.map((c) => {
          const mine = items.filter((it) => colOf(it) === c.id);
          return (
            <div key={c.id} role="region" aria-label={c.title} className={`quadrant${over === c.id ? " over" : ""}`}
              onDragOver={(e) => { e.preventDefault(); setOver(c.id); }} onDragLeave={() => setOver("")}
              onDrop={(e) => { e.preventDefault(); setOver(""); move(e.dataTransfer.getData("text/plain"), c.id); }}>
              <div className="quadrant-head">
                <span className="title">{c.title}</span>
                <span className="count">{mine.filter((it) => !it.done).length}</span>
              </div>
              {c.hint && <span className="hint">{c.hint}</span>}
              <ul className="qitems">
                {mine.map((it) => (
                  <li key={it.id} className={`qitem${it.done ? " done" : ""}`} draggable data-testid={`item-${it.title}`}
                    onDragStart={(e) => { e.dataTransfer.setData("text/plain", it.id); e.dataTransfer.effectAllowed = "move"; }}>
                    <input type="checkbox" checked={!!it.done} onChange={() => toggle(it)} aria-label={`Done: ${it.title}`} />
                    <span className="grow">
                      <span className="title">{it.title}</span>
                      {(it.note || it.due) && <span className="meta">{[it.due, it.note].filter(Boolean).join(" · ")}</span>}
                    </span>
                    <select className="input move" aria-label={`Move ${it.title}`} value={c.id} onChange={(e) => move(it.id, e.target.value)}>
                      {columns.map((o) => <option key={o.id} value={o.id}>{o.title}</option>)}
                    </select>
                  </li>
                ))}
              </ul>
              <form className="qadd" onSubmit={(e) => add(e, c.id)}>
                <input className="input" aria-label={`Add to ${c.title}`} placeholder="Add a task…" maxLength={200}
                  value={drafts[c.id] ?? ""} onChange={(e) => setDrafts((d) => ({ ...d, [c.id]: e.target.value }))} />
              </form>
            </div>
          );
        })}
      </div>
    </section>
  );
}

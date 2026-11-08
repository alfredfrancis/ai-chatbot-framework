/**
 * The components an OpenUI Lang screen may use (https://openui.com): personal apps (apps/<id>/app.oui) and
 * views the agent puts in a chat reply (an ```openui block). This library is the only vocabulary the agent
 * has, so every screen is built from these design-system components (no HTML, no styles). The agent learns
 * the language from a reference generated from this file (scripts/build-openui-prompt.mjs → the openui skill),
 * so a component's description is written for the model.
 */
import { action, createLibrary, defineComponent, reactive, useStateField, useTriggerAction } from "@openuidev/react-lang";
import { createContext, useContext, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { z } from "zod/v4";
import { BarChart, LineChart, PieChart, Progress } from "./charts";

/** What components reach outside the screen with: the app's action API (see pages/AppView.tsx). Null in a chat. */
export type AppApi = { act: (action: string, args: Record<string, unknown>) => Promise<Record<string, unknown> | null> };
export const AppApiContext = createContext<AppApi | null>(null);

const nodes = z.array(z.any());
const tone = z.enum(["neutral", "success", "warning", "danger"]);

const Screen = defineComponent({
  name: "Screen",
  description: "The whole screen (an app, or a view in a chat reply): its sections from top to bottom.",
  props: z.object({ children: nodes.describe("Sections, top to bottom") }),
  component: ({ props, renderNode }) => <div className="oui-screen">{renderNode(props.children)}</div>,
});

const Row = defineComponent({
  name: "Row",
  description: "Puts components side by side; they stack on phones.",
  props: z.object({ children: nodes }),
  component: ({ props, renderNode }) => <div className="oui-row">{renderNode(props.children)}</div>,
});

const Grid = defineComponent({
  name: "Grid",
  description: "Equal columns (2-4) of cards or stats; one column on phones.",
  props: z.object({ children: nodes, columns: z.number().int().min(2).max(4).optional() }),
  component: ({ props, renderNode }) => (
    <div className="oui-grid" data-columns={props.columns ?? 2}>{renderNode(props.children)}</div>
  ),
});

const Card = defineComponent({
  name: "Card",
  description: "A titled section.",
  props: z.object({ title: z.string(), children: nodes.optional(), description: z.string().optional() }),
  component: ({ props, renderNode }) => (
    <section className="card oui-card" aria-label={props.title}>
      <div><h2>{props.title}</h2>{props.description && <p className="hint">{props.description}</p>}</div>
      {renderNode(props.children ?? [])}
    </section>
  ),
});

const Heading = defineComponent({
  name: "Heading",
  description: "A section heading outside a Card.",
  props: z.object({ text: z.string() }),
  component: ({ props }) => <h2>{props.text}</h2>,
});

const Text = defineComponent({
  name: "Text",
  description: "Markdown text (bold, lists, links, tables). Use for briefs and notes, e.g. Text(brief.text).",
  props: z.object({ markdown: z.string() }),
  component: ({ props }) =>
    props.markdown?.trim() ? (
      <div className="answer"><Markdown remarkPlugins={[remarkGfm]}>{props.markdown}</Markdown></div>
    ) : <p className="hint">Nothing here yet.</p>,
});

const Stat = defineComponent({
  name: "Stat",
  description: "One number or short value with a label, e.g. Stat(\"Due today\", @Count(due)).",
  props: z.object({ label: z.string(), value: z.union([z.string(), z.number()]), note: z.string().optional() }),
  component: ({ props }) => (
    <div className="oui-stat">
      <span className="label">{props.label}</span>
      <span className="value">{props.value}</span>
      {props.note && <span className="hint">{props.note}</span>}
    </div>
  ),
});

const Badge = defineComponent({
  name: "Badge",
  description: "A short status label.",
  props: z.object({ text: z.string(), tone: tone.optional() }),
  component: ({ props }) => <span className={`badge ${props.tone && props.tone !== "neutral" ? props.tone : "plain"}`}>{props.text}</span>,
});

const Notice = defineComponent({
  name: "Notice",
  description: "A one-line message that stands out: a warning, a problem, or good news.",
  props: z.object({ text: z.string(), tone: tone.optional() }),
  component: ({ props }) => <div className={`oui-notice ${props.tone ?? "neutral"}`} role="note">{props.text}</div>,
});

const Table = defineComponent({
  name: "Table",
  description: "Rows of values under column headings. rows is a list of rows, each a list of cells.",
  props: z.object({ columns: z.array(z.string()), rows: z.array(z.array(z.union([z.string(), z.number(), z.null()]))) }),
  component: ({ props }) => (
    <div className="oui-table-wrap">
      <table className="oui-table">
        <thead><tr>{props.columns.map((c, i) => <th key={i} scope="col">{c}</th>)}</tr></thead>
        <tbody>{(props.rows ?? []).map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{c ?? ""}</td>)}</tr>)}</tbody>
      </table>
    </div>
  ),
});


const Tab = defineComponent({
  name: "Tab",
  description: "One page of Tabs: a title and what it shows.",
  props: z.object({ title: z.string(), children: nodes }),
  component: ({ props, renderNode }) => <div className="oui-screen">{renderNode(props.children)}</div>,
});

const Tabs = defineComponent({
  name: "Tabs",
  description: "Pages the user switches between, one shown at a time, e.g. Tabs([Tab(\"This week\", [...]), Tab(\"Next week\", [...])]).",
  props: z.object({ tabs: z.array(Tab.ref) }),
  component: function TabsView({ props, renderNode }) {
    const tabs = (props.tabs ?? []) as unknown as { props?: { title?: string; children?: unknown[] } }[];
    const [open, setOpen] = useState(0);
    const at = Math.min(open, Math.max(0, tabs.length - 1));
    const base = useRef(`oui-tabs-${tabSeq++}`).current;
    const keys = (e: KeyboardEvent<HTMLButtonElement>) => {
      const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
      if (!d) return;
      const next = (at + d + tabs.length) % tabs.length;
      setOpen(next);
      document.getElementById(`${base}-t${next}`)?.focus();
    };
    return (
      <div className="oui-tabs">
        <div className="seg" role="tablist">
          {tabs.map((t, i) => (
            <button key={i} id={`${base}-t${i}`} className="btn ghost sm" role="tab" aria-selected={i === at} aria-pressed={i === at}
              aria-controls={`${base}-p${i}`} tabIndex={i === at ? 0 : -1} onClick={() => setOpen(i)} onKeyDown={keys}>
              {t?.props?.title ?? `Tab ${i + 1}`}
            </button>
          ))}
        </div>
        {tabs[at] && (
          <div role="tabpanel" id={`${base}-p${at}`} aria-labelledby={`${base}-t${at}`}>
            <div className="oui-screen">{renderNode(tabs[at].props?.children ?? [])}</div>
          </div>
        )}
      </div>
    );
  },
});
let tabSeq = 0;

const Collapsible = defineComponent({
  name: "Collapsible",
  description: "A section the user opens to see more (details, the full list, the method). Closed unless open is true.",
  props: z.object({ title: z.string(), children: nodes, open: z.boolean().optional() }),
  component: ({ props, renderNode }) => (
    <details className="oui-collapsible" open={props.open ?? false}>
      <summary>{props.title}</summary>
      <div className="oui-screen">{renderNode(props.children ?? [])}</div>
    </details>
  ),
});

const List = defineComponent({
  name: "List",
  description:
    "Rows of items with a title, an optional note under it and an optional badge on the right, " +
    "e.g. List([{title: \"Dentist\", note: \"Tue 9:30\", badge: \"Booked\", tone: \"success\"}]).",
  props: z.object({
    items: z.array(z.object({ title: z.string(), note: z.string().optional(), badge: z.string().optional(), tone: tone.optional() })),
  }),
  component: ({ props }) =>
    (props.items ?? []).length ? (
      <ul className="oui-list">
        {props.items.map((it, i) => (
          <li key={i}>
            <span className="grow"><span className="title">{it.title}</span>{it.note && <span className="hint">{it.note}</span>}</span>
            {it.badge && <span className={`badge ${it.tone && it.tone !== "neutral" ? it.tone : "plain"}`}>{it.badge}</span>}
          </li>
        ))}
      </ul>
    ) : <p className="hint">Nothing here yet.</p>,
});

const Steps = defineComponent({
  name: "Steps",
  description: "Numbered steps in order (a plan, a how-to, a timeline); done steps show ticked.",
  props: z.object({ items: z.array(z.object({ title: z.string(), note: z.string().optional(), done: z.boolean().optional() })) }),
  component: ({ props }) => (
    <ol className="oui-steps">
      {(props.items ?? []).map((it, i) => (
        <li key={i} className={it.done ? "done" : ""}>
          <span className="num" aria-hidden="true">{it.done ? "✓" : i + 1}</span>
          <span className="grow"><span className="title">{it.title}{it.done && <span className="sr-only"> (done)</span>}</span>
            {it.note && <span className="hint">{it.note}</span>}</span>
        </li>
      ))}
    </ol>
  ),
});

const Button = defineComponent({
  name: "Button",
  description:
    "A button. Without an action it sends its label to the agent. Use the primary variant for at most one main action. " +
    "confirm is a question shown before it runs (use it for anything the user can't undo).",
  props: z.object({
    label: z.string(),
    action: action().optional(),
    variant: z.enum(["primary", "secondary", "ghost", "danger"]).optional(),
    confirm: z.string().optional(),
  }),
  component: function ButtonView({ props }) {
    const trigger = useTriggerAction();
    const [asking, setAsking] = useState(false);
    const run = () => { setAsking(false); trigger(props.label, undefined, props.action as never); };
    const cls = { primary: "btn primary", secondary: "btn", ghost: "btn ghost", danger: "btn danger" }[props.variant ?? "secondary"];
    if (asking) {
      return (
        <span className="oui-confirm" role="alertdialog" aria-label={props.label}>
          <span>{props.confirm}</span>
          <button className="btn primary sm" onClick={run}>Yes, {props.label.toLowerCase()}</button>
          <button className="btn ghost sm" onClick={() => setAsking(false)}>Cancel</button>
        </span>
      );
    }
    return <button className={cls} onClick={() => (props.confirm ? setAsking(true) : run())}>{props.label}</button>;
  },
});

const fieldId = (label: string) => `oui-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;

const TextField = defineComponent({
  name: "TextField",
  description: "A one-line text box bound to a $variable, e.g. TextField(\"New task\", $title).",
  props: z.object({ label: z.string(), value: reactive(z.string().optional()), placeholder: z.string().optional() }),
  component: function TextFieldView({ props }) {
    const field = useStateField(fieldId(props.label), props.value);
    return (
      <div className="field">
        <label htmlFor={fieldId(props.label)}>{props.label}</label>
        <input id={fieldId(props.label)} className="input" value={String(field.value ?? "")} placeholder={props.placeholder}
          maxLength={2000} onChange={(e) => field.setValue(e.target.value)} />
      </div>
    );
  },
});

const SelectField = defineComponent({
  name: "SelectField",
  description: "A dropdown bound to a $variable. options are {value, label} objects.",
  props: z.object({
    label: z.string(),
    options: z.array(z.object({ value: z.string(), label: z.string() })),
    value: reactive(z.string().optional()),
  }),
  component: function SelectFieldView({ props }) {
    const field = useStateField(fieldId(props.label), props.value);
    return (
      <div className="field">
        <label htmlFor={fieldId(props.label)}>{props.label}</label>
        <select id={fieldId(props.label)} className="input" value={String(field.value ?? "")} onChange={(e) => field.setValue(e.target.value)}>
          {(props.options ?? []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>
    );
  },
});


const TextArea = defineComponent({
  name: "TextArea",
  description: "A multi-line text box bound to a $variable, for notes or a longer answer.",
  props: z.object({ label: z.string(), value: reactive(z.string().optional()), placeholder: z.string().optional() }),
  component: function TextAreaView({ props }) {
    const field = useStateField(fieldId(props.label), props.value);
    return (
      <div className="field">
        <label htmlFor={fieldId(props.label)}>{props.label}</label>
        <textarea id={fieldId(props.label)} className="input" rows={4} value={String(field.value ?? "")} placeholder={props.placeholder}
          maxLength={10000} onChange={(e) => field.setValue(e.target.value)} />
      </div>
    );
  },
});

const NumberField = defineComponent({
  name: "NumberField",
  description: "A number box bound to a $variable, e.g. NumberField(\"Budget\", $budget, 0).",
  props: z.object({ label: z.string(), value: reactive(z.number().optional()), min: z.number().optional(), max: z.number().optional(), step: z.number().optional() }),
  component: function NumberFieldView({ props }) {
    const field = useStateField(fieldId(props.label), props.value);
    return (
      <div className="field">
        <label htmlFor={fieldId(props.label)}>{props.label}</label>
        <input id={fieldId(props.label)} className="input" type="number" inputMode="decimal" min={props.min} max={props.max} step={props.step ?? "any"}
          value={field.value == null ? "" : String(field.value)} onChange={(e) => field.setValue(e.target.value === "" ? undefined : Number(e.target.value))} />
      </div>
    );
  },
});

const DateField = defineComponent({
  name: "DateField",
  description: "A date picker bound to a $variable; the value is YYYY-MM-DD.",
  props: z.object({ label: z.string(), value: reactive(z.string().optional()) }),
  component: function DateFieldView({ props }) {
    const field = useStateField(fieldId(props.label), props.value);
    return (
      <div className="field">
        <label htmlFor={fieldId(props.label)}>{props.label}</label>
        <input id={fieldId(props.label)} className="input" type="date" value={String(field.value ?? "")} onChange={(e) => field.setValue(e.target.value)} />
      </div>
    );
  },
});

const Checkbox = defineComponent({
  name: "Checkbox",
  description: "A yes/no tick box bound to a $variable (true or false).",
  props: z.object({ label: z.string(), value: reactive(z.boolean().optional()) }),
  component: function CheckboxView({ props }) {
    const field = useStateField(fieldId(props.label), props.value);
    return (
      <label className="oui-check">
        <input type="checkbox" checked={!!field.value} onChange={(e) => field.setValue(e.target.checked)} />
        <span>{props.label}</span>
      </label>
    );
  },
});

const RadioGroup = defineComponent({
  name: "RadioGroup",
  description: "One choice from a few options, all visible (use SelectField for many). options are {value, label} objects.",
  props: z.object({
    label: z.string(),
    options: z.array(z.object({ value: z.string(), label: z.string() })),
    value: reactive(z.string().optional()),
  }),
  component: function RadioGroupView({ props }) {
    const field = useStateField(fieldId(props.label), props.value);
    return (
      <fieldset className="oui-radios">
        <legend className="label">{props.label}</legend>
        {(props.options ?? []).map((o) => (
          <label key={o.value} className={`choice${field.value === o.value ? " on" : ""}`}>
            <input type="radio" name={fieldId(props.label)} value={o.value} checked={field.value === o.value} onChange={() => field.setValue(o.value)} />
            <span className="title">{o.label}</span>
          </label>
        ))}
      </fieldset>
    );
  },
});

const Slider = defineComponent({
  name: "Slider",
  description: "A slider for a number in a range, bound to a $variable, e.g. Slider(\"Hours a week\", $hours, 0, 40).",
  props: z.object({ label: z.string(), value: reactive(z.number().optional()), min: z.number(), max: z.number(), step: z.number().optional() }),
  component: function SliderView({ props }) {
    const field = useStateField(fieldId(props.label), props.value);
    const v = typeof field.value === "number" ? field.value : props.min;
    return (
      <div className="field oui-slider">
        <label htmlFor={fieldId(props.label)}>{props.label} <span className="value">{v}</span></label>
        <input id={fieldId(props.label)} type="range" min={props.min} max={props.max} step={props.step ?? 1} value={v}
          onChange={(e) => field.setValue(Number(e.target.value))} />
      </div>
    );
  },
});

type BoardItem = { id: string; title: string; column: string; note?: string; due?: string; done?: boolean };
type Column = { id: string; title: string; hint?: string };

const Board = defineComponent({
  name: "Board",
  description:
    "Columns of items the user drags between, ticks done and adds to; it reads and saves a JSON file " +
    "{\"items\": [{\"id\", \"title\", \"column\", \"note\"?, \"due\"?, \"done\"?}]} by itself (column is a column id). " +
    "Four columns show as a 2x2 matrix. agentNote, if set, is sent to the agent with each change - only set it when " +
    "the agent must react, since each change then costs a run. Apps only.",
  props: z.object({
    title: z.string(),
    file: z.string().describe("Workspace path of the JSON file, e.g. apps/cockpit/tasks.json"),
    columns: z.array(z.object({ id: z.string(), title: z.string(), hint: z.string().optional() })),
    agentNote: z.string().optional(),
  }),
  component: function BoardComponent({ props }) {
    const api = useContext(AppApiContext);
    if (!api) return <div className="oui-notice neutral" role="note">A board works in a personal app, not in a chat.</div>;
    return <BoardView {...props} act={api.act} />;
  },
});

function BoardView({ title, file, columns: cols, agentNote, act }: { title: string; file: string; columns: Column[]; agentNote?: string; act: AppApi["act"] }) {
  const [items, setItems] = useState<BoardItem[] | null>(null);
  const [extra, setExtra] = useState<Record<string, unknown>>({});
  const [over, setOver] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const writes = useRef(0); // a read that started before a write shows the file from before it
  const queue = useRef<Promise<unknown>>(Promise.resolve()); // one write at a time, in order

  useEffect(() => {
    let live = true;
    const load = async () => {
      const seen = writes.current;
      const r = await act("read_file", { path: file });
      const data = (r?.data ?? {}) as { items?: unknown };
      if (!live || seen !== writes.current) return;
      const list = Array.isArray(data.items) ? (data.items as BoardItem[]).filter((i) => i && typeof i === "object") : [];
      setItems(list);
      setExtra(data && typeof data === "object" ? (data as Record<string, unknown>) : {});
    };
    load();
    const t = setInterval(() => { if (document.visibilityState === "visible") load(); }, 4000);
    return () => { live = false; clearInterval(t); };
  }, [act, file]);

  const columns = cols?.length ? cols : [{ id: "todo", title: "To-do" }];
  const known = new Set(columns.map((c) => c.id));
  const colOf = (it: BoardItem) => (known.has(it.column) ? it.column : columns[0].id);
  const titleOf = (col: string) => columns.find((c) => c.id === col)?.title ?? col;
  const list = items ?? [];

  const save = (next: BoardItem[], event: string) => {
    setItems(next);
    writes.current++;
    const content = JSON.stringify({ ...extra, items: next }, null, 2) + "\n";
    queue.current = queue.current.then(async () => {
      const ok = await act("update_file", { path: file, content });
      writes.current++;
      if (ok && agentNote) await act("ask_agent", { prompt: agentNote, event });
    });
  };
  const move = (itemId: string, to: string) => {
    const it = list.find((x) => x.id === itemId);
    if (!it || colOf(it) === to) return;
    save(list.map((x) => (x.id === itemId ? { ...x, column: to } : x)), `Moved "${it.title}" from "${titleOf(colOf(it))}" to "${titleOf(to)}" in ${title}.`);
  };
  const toggle = (it: BoardItem) =>
    save(list.map((x) => (x.id === it.id ? { ...x, done: !x.done } : x)), `Marked "${it.title}" as ${it.done ? "not done" : "done"} in ${title}.`);
  const add = (e: FormEvent, col: string) => {
    e.preventDefault();
    const text = (drafts[col] ?? "").trim();
    if (!text) return;
    setDrafts((d) => ({ ...d, [col]: "" }));
    save([...list, { id: `u${Date.now().toString(36)}`, title: text, column: col, done: false }], `Added "${text}" to "${titleOf(col)}" in ${title}.`);
  };

  return (
    <section className="stack" aria-label={title}>
      <h2>{title}</h2>
      <div className={`board${columns.length === 4 ? " matrix" : ""}`} aria-busy={items === null}>
        {columns.map((c) => {
          const mine = list.filter((it) => colOf(it) === c.id);
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

export const openuiLibrary = createLibrary({
  root: "Screen",
  components: [
    Screen, Row, Grid, Card, Tabs, Tab, Collapsible, Heading, Text, Stat, Badge, Notice, List, Steps, Table,
    BarChart, LineChart, PieChart, Progress,
    Button, TextField, TextArea, NumberField, DateField, SelectField, RadioGroup, Checkbox, Slider, Board,
  ],
  componentGroups: [
    { name: "Layout", components: ["Screen", "Row", "Grid", "Card", "Tabs", "Tab", "Collapsible"] },
    { name: "Content", components: ["Heading", "Text", "Stat", "Badge", "Notice", "List", "Steps", "Table"] },
    {
      name: "Charts",
      components: ["BarChart", "LineChart", "PieChart", "Progress"],
      notes: ["Pick the chart for the question: BarChart compares, LineChart shows a trend, PieChart shows shares of a whole, Progress shows how far along."],
    },
    {
      name: "Actions and inputs",
      components: ["Button", "TextField", "TextArea", "NumberField", "DateField", "SelectField", "RadioGroup", "Checkbox", "Slider"],
      notes: ["Inputs only hold a $variable; a Button uses it, e.g. Button(\"Plan it\", @ToAssistant(\"Plan a trip for \" + $days + \" days\"))."],
    },
    { name: "Apps only", components: ["Board"] },
  ],
});

/** The tools an app's Query() and Mutation() can call: the app action API (backend/acf/apps.py). */
export const APP_TOOLS = [
  {
    name: "read_file",
    description: "Read a file of the app (its folder, or a file listed in app.json). Returns {text}, plus {data} when the file is JSON.",
    inputSchema: { type: "object", properties: { path: { type: "string" } }, required: ["path"] },
    outputSchema: { type: "object", properties: { text: { type: "string" }, data: {} } },
    annotations: { readOnlyHint: true },
  },
  {
    name: "update_file",
    description: "Write a file of the app. content is text, or any value, which is saved as JSON.",
    inputSchema: { type: "object", properties: { path: { type: "string" }, content: {} }, required: ["path", "content"] },
    outputSchema: { type: "object", properties: { path: { type: "string" } } },
  },
  {
    name: "ask_agent",
    description: "Send the agent a message in the app's own chat; it works in the background. Prefer @ToAssistant in buttons.",
    inputSchema: { type: "object", properties: { prompt: { type: "string" } }, required: ["prompt"] },
    outputSchema: { type: "object", properties: { chat_id: { type: "number" } } },
  },
  {
    name: "run",
    description: "Run the script apps/<id>/actions/<script>.sh in the sandbox with input as JSON in $1. Returns {output}.",
    inputSchema: { type: "object", properties: { script: { type: "string" }, input: {} }, required: ["script"] },
    outputSchema: { type: "object", properties: { output: { type: "string" } } },
  },
  {
    name: "mcp",
    description:
      "Call a read-only tool of a connected app (e.g. a calendar search). Returns {text}, plus {data} when it is JSON. " +
      "Tools that change things are refused: send those to the agent instead.",
    inputSchema: {
      type: "object",
      properties: { server: { type: "string" }, tool: { type: "string" }, arguments: { type: "object" } },
      required: ["server", "tool"],
    },
    outputSchema: { type: "object", properties: { text: { type: "string" }, data: {} } },
    annotations: { readOnlyHint: true },
  },
];

export const COCKPIT_EXAMPLE = `root = Screen([summary, needs, todo, actions])
brief = Query("read_file", {path: "apps/cockpit/brief.md"}, {text: ""}, 10)
tasks = Query("read_file", {path: "apps/cockpit/tasks.json"}, {data: {items: []}}, 10)
summary = Grid([Stat("Open to-dos", @Count(@Filter(tasks.data.items, "done", "==", false))), Stat("Do first", @Count(@Filter(tasks.data.items, "column", "==", "do")))], 2)
needs = Card("Needs you", [Text(brief.text)])
todo = Board("To-do", "apps/cockpit/tasks.json", [{id: "do", title: "Do first", hint: "Urgent and important"}, {id: "schedule", title: "Schedule", hint: "Important, not urgent"}, {id: "delegate", title: "Delegate", hint: "Urgent, not important"}, {id: "drop", title: "Drop", hint: "Neither"}])
actions = Row([Button("Refresh", @ToAssistant("Use the personal-assistant skill to refresh the cockpit."), "primary"), Button("Plan my day", @ToAssistant("Plan my day from the cockpit's Do first and Schedule columns."))])`;

export const CHAT_EXAMPLE = `root = Screen([spend, split, pick])
$food = 300
spend = BarChart("Spending by month", ["Aug", "Sep", "Oct"], [{name: "Food", values: [320, 280, 345]}, {name: "Travel", values: [120, 410, 90]}], "EUR")
split = PieChart("October", [{label: "Food", value: 345}, {label: "Travel", value: 90}, {label: "Home", value: 610}], "EUR")
pick = Card("Set a budget", [Slider("Monthly food budget", $food, 200, 500, 10), Button("Track it", @ToAssistant("Track my food spending against a budget of " + $food + " EUR a month."), "primary")])`;

export const RULES = [
  "Write only these components; never HTML, CSS or colours - the look comes from the design system.",
  "Every program starts with root = Screen([...]) on its first line.",
  "In a chat reply: write the program in a fenced code block whose language is openui, with your text before or after it. " +
    "Put the numbers in the program itself; Query, Mutation, @Run and Board do not work in chat. " +
    "A Button with @ToAssistant(\"...\") sends that text to you in the same chat, as if the user typed it.",
  "In a personal app: the tools above are called by the app screen, not by you; to see a file's shape, read it with your own read tool. " +
    "Read data with Query(\"read_file\", ...) and a refresh interval (e.g. 10) so the screen follows the files you update.",
  "Buttons that need judgment, writing or another app's write tools send the work to you with @ToAssistant(\"...\").",
  "Keep a screen focused on what the user acts on; at most one primary Button.",
];

/** The OpenUI Lang reference the agent reads (the built-in openui skill's reference.md). */
export function openuiPrompt(): string {
  return openuiLibrary.prompt({
    preamble:
      "OpenUI Lang describes a screen built from the components below. It is used in two places: a view inside a chat " +
      "reply (a fenced ```openui block) and a personal app (the file apps/<id>/app.oui). Both hold one program whose " +
      "root is Screen(...). The tools listed under Query are available in personal apps only. " +
      "This is the complete reference for the language and the components available.",
    tools: APP_TOOLS,
    examples: [CHAT_EXAMPLE],
    toolExamples: [COCKPIT_EXAMPLE],
    additionalRules: RULES,
  });
}

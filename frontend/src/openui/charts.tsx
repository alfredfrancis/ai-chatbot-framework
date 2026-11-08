/**
 * Charts for OpenUI Lang screens (personal apps and chat replies). Data colours are the design system's
 * two data colours (accent, accent-2) and their lighter steps; labels are HTML so they keep the text floor
 * at any width, and every chart carries its numbers as a table for screen readers.
 */
import { defineComponent } from "@openuidev/react-lang";
import type { ReactNode } from "react";
import { z } from "zod/v4";

const series = z.array(z.object({ name: z.string(), values: z.array(z.number().nullable()) }));
type Series = z.infer<typeof series>;

const num = (v: unknown) => (typeof v === "number" && Number.isFinite(v) ? v : 0);
const fmt = (v: number) => (Math.abs(v) >= 1000 ? v.toLocaleString() : String(Math.round(v * 100) / 100));
/** A round top for the axis: 1, 2, 2.5 or 5 times a power of ten. */
function niceMax(v: number) {
  if (v <= 0) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  return ([1, 2, 2.5, 5, 10].find((m) => m * p >= v) ?? 10) * p;
}

function DataTable({ title, labels, rows }: { title: string; labels: string[]; rows: Series }) {
  return (
    <table className="sr-only">
      <caption>{title}</caption>
      <thead><tr><th scope="col">Label</th>{rows.map((s, i) => <th key={i} scope="col">{s.name}</th>)}</tr></thead>
      <tbody>{labels.map((l, i) => <tr key={i}><th scope="row">{l}</th>{rows.map((s, j) => <td key={j}>{s.values?.[i] ?? ""}</td>)}</tr>)}</tbody>
    </table>
  );
}

function Legend({ names }: { names: string[] }) {
  if (names.length < 2) return null;
  return (
    <ul className="oui-legend" aria-hidden="true">
      {names.map((n, i) => <li key={i}><span className={`swatch c${i % 6}`} />{n}</li>)}
    </ul>
  );
}

function Figure({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <figure className="oui-chart" aria-label={title || "Chart"}>
      {title && <figcaption>{title}</figcaption>}
      {children}
    </figure>
  );
}

export const BarChart = defineComponent({
  name: "BarChart",
  description:
    "Bars for comparing amounts across labels. series is a list of {name, values}, one value per label; " +
    "several series show side by side. E.g. BarChart(\"Spend\", [\"Jan\", \"Feb\"], [{name: \"Food\", values: [320, 280]}]).",
  props: z.object({ title: z.string(), labels: z.array(z.string()), series, unit: z.string().optional() }),
  component: ({ props }) => {
    const labels = props.labels ?? [];
    const rows = (props.series ?? []).slice(0, 6);
    const top = niceMax(Math.max(0, ...rows.flatMap((s) => (s.values ?? []).map(num))));
    const unit = props.unit ? ` ${props.unit}` : "";
    return (
      <Figure title={props.title}>
        <div className="oui-bars" aria-hidden="true">
          <span className="axis">{fmt(top)}{unit}</span>
          <div className="plot">
            {labels.map((l, i) => (
              <div key={i} className="group">
                <div className="bars">
                  {rows.map((s, j) => {
                    const v = num(s.values?.[i]);
                    return <span key={j} className={`bar c${j}`} style={{ height: `${Math.max(0, (v / top) * 100)}%` }} title={`${s.name} · ${l}: ${fmt(v)}${unit}`} />;
                  })}
                </div>
                <span className="tick">{l}</span>
              </div>
            ))}
          </div>
        </div>
        <Legend names={rows.map((s) => s.name)} />
        <DataTable title={props.title} labels={labels} rows={rows} />
      </Figure>
    );
  },
});

export const LineChart = defineComponent({
  name: "LineChart",
  description: "Lines for a trend over time. labels are the points in order (dates, months); series as in BarChart.",
  props: z.object({ title: z.string(), labels: z.array(z.string()), series, unit: z.string().optional() }),
  component: ({ props }) => {
    const labels = props.labels ?? [];
    const rows = (props.series ?? []).slice(0, 6);
    const all = rows.flatMap((s) => (s.values ?? []).filter((v): v is number => typeof v === "number"));
    const lo = Math.min(0, ...all);
    const hi = niceMax(Math.max(0, ...all) - lo) + lo;
    const n = Math.max(labels.length, 2);
    const x = (i: number) => (i / (n - 1)) * 100;
    const y = (v: number) => 100 - ((v - lo) / (hi - lo || 1)) * 100;
    const unit = props.unit ? ` ${props.unit}` : "";
    const ends = labels.length > 6 ? [labels[0], labels[Math.floor((labels.length - 1) / 2)], labels[labels.length - 1]] : labels;
    return (
      <Figure title={props.title}>
        <div className="oui-line" aria-hidden="true">
          <span className="axis">{fmt(hi)}{unit}</span>
          <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="plot">
            {[25, 50, 75].map((g) => <line key={g} x1="0" x2="100" y1={g} y2={g} className="grid" vectorEffect="non-scaling-stroke" />)}
            {rows.map((s, j) => {
              const pts = (s.values ?? []).map((v, i) => (typeof v === "number" ? `${x(i)},${y(v)}` : null)).filter(Boolean).join(" ");
              return <polyline key={j} points={pts} className={`series c${j}`} vectorEffect="non-scaling-stroke" />;
            })}
          </svg>
          <span className="axis">{fmt(lo)}{unit}</span>
          <div className="ticks">{ends.map((l, i) => <span key={i}>{l}</span>)}</div>
        </div>
        <Legend names={rows.map((s) => s.name)} />
        <DataTable title={props.title} labels={labels} rows={rows} />
      </Figure>
    );
  },
});

export const PieChart = defineComponent({
  name: "PieChart",
  description: "A ring showing how a whole splits into parts (at most 6; the rest is grouped as Other). slices are {label, value}.",
  props: z.object({ title: z.string(), slices: z.array(z.object({ label: z.string(), value: z.number() })), unit: z.string().optional() }),
  component: ({ props }) => {
    let slices = (props.slices ?? []).filter((s) => num(s.value) > 0);
    if (slices.length > 6) {
      const sorted = [...slices].sort((a, b) => b.value - a.value);
      slices = [...sorted.slice(0, 5), { label: "Other", value: sorted.slice(5).reduce((t, s) => t + s.value, 0) }];
    }
    const total = slices.reduce((t, s) => t + s.value, 0) || 1;
    const r = 15.915; // circumference 100
    let at = 0;
    const unit = props.unit ? ` ${props.unit}` : "";
    return (
      <Figure title={props.title}>
        <div className="oui-pie">
          <svg viewBox="0 0 42 42" aria-hidden="true">
            <circle cx="21" cy="21" r={r} className="track" />
            {slices.map((s, i) => {
              const part = (s.value / total) * 100;
              const el = <circle key={i} cx="21" cy="21" r={r} className={`slice c${i}`} strokeDasharray={`${part} ${100 - part}`} strokeDashoffset={25 - at} />;
              at += part;
              return el;
            })}
          </svg>
          <ul className="oui-legend vertical">
            {slices.map((s, i) => (
              <li key={i}><span className={`swatch c${i}`} aria-hidden="true" />{s.label}
                <span className="value">{fmt(s.value)}{unit} · {Math.round((s.value / total) * 100)}%</span></li>
            ))}
          </ul>
        </div>
      </Figure>
    );
  },
});

export const Progress = defineComponent({
  name: "Progress",
  description: "A bar showing how far along something is, e.g. Progress(\"Budget used\", 420, 600).",
  props: z.object({
    label: z.string(),
    value: z.number(),
    max: z.number().optional(),
    tone: z.enum(["neutral", "success", "warning", "danger"]).optional(),
  }),
  component: ({ props }) => {
    const max = num(props.max) || 100;
    const value = num(props.value);
    const pct = Math.max(0, Math.min(100, (value / max) * 100));
    return (
      <div className="oui-progress">
        <div className="head"><span className="label">{props.label}</span><span className="hint">{props.max ? `${fmt(value)} of ${fmt(max)}` : `${Math.round(pct)}%`}</span></div>
        <div className={`track ${props.tone ?? "neutral"}`} role="progressbar" aria-label={props.label}
          aria-valuemin={0} aria-valuemax={max} aria-valuenow={value}>
          <span style={{ width: `${pct}%` }} />
        </div>
      </div>
    );
  },
});

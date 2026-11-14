// Generates src/tokens.css from design/tokens.json (the design system's tokens; edit those, not the CSS),
// and the root DESIGN.md (the DESIGN.md format: tokens as YAML frontmatter + design/README.md as the body).
// Dark is the first theme and the default; light applies when the OS prefers light.
import { readFileSync, writeFileSync } from "node:fs";

// Paths are relative to this script, so it works in the repo and in Docker builds.
const tokens = JSON.parse(readFileSync(new URL("../../design/tokens.json", import.meta.url), "utf8"));
const [first, ...others] = tokens.color.themes.map((t) => t.id);

const value = (t, theme) => (typeof t.value === "string" ? t.value : t.value[theme] ?? t.value[first]);
const ref = (v) => (typeof v === "string" && v.startsWith("{") ? `var(--${v.slice(1, -1)})` : v);
const themed = [...tokens.color.tokens, ...(tokens.shadow?.tokens ?? [])];
const flat = ["spacing", "radius", "size"].flatMap((k) => tokens[k]?.tokens ?? []);

const block = (theme) => themed.map((t) => `  --${t.name}: ${ref(value(t, theme))};`).join("\n");
let css = `/* Generated from design/tokens.json by scripts/build-tokens.mjs. Do not edit. */\n:root {\n${block(first)}\n`;
css += Object.entries(tokens.type.families).map(([k, v]) => `  --font-${k}: ${v};`).join("\n") + "\n";
css += flat.map((t) => `  --${t.name}: ${t.value};`).join("\n") + `\n  color-scheme: ${first};\n}\n`;
for (const theme of others) {
  const changed = themed.filter((t) => value(t, theme) !== value(t, first));
  css += `\n@media (prefers-color-scheme: ${theme}) {\n  :root {\n${changed.map((t) => `    --${t.name}: ${ref(value(t, theme))};`).join("\n")}\n    color-scheme: ${theme};\n  }\n}\n`;
}
writeFileSync(new URL("../src/tokens.css", import.meta.url), css);

// DESIGN.md: frontmatter from the tokens (first theme's colours, then the others' where they differ, as
// <name>-<theme>), body from the brand book. Strings are JSON-quoted, which is valid YAML.
const q = JSON.stringify;
const byName = Object.fromEntries(flat.map((t) => [t.name, t.value]));
const lines = ["---", `name: ${q(tokens.name)}`, `description: ${q("A self-hosted AI agent for people who don't write code. Dark first; light mirrors it.")}`, "colors:"];
for (const t of tokens.color.tokens) lines.push(`  ${t.name}: ${q(value(t, first))}`);
for (const theme of others) {
  for (const t of tokens.color.tokens) if (value(t, theme) !== value(t, first)) lines.push(`  ${t.name}-${theme}: ${q(value(t, theme))}`);
}
lines.push("typography:");
for (const s of tokens.type.groups.flatMap((g) => g.styles.map((st) => ({ ...st, family: g.family })))) {
  lines.push(`  ${s.name}:`, `    fontFamily: ${q(tokens.type.families[s.family])}`, `    fontSize: ${q(s.fontSize)}`,
    `    fontWeight: ${s.fontWeight}`, `    lineHeight: ${q(s.lineHeight)}`, ...(s.letterSpacing ? [`    letterSpacing: ${q(s.letterSpacing)}`] : []));
}
lines.push("rounded:", ...tokens.radius.tokens.map((t) => `  ${t.name.replace(/^radius-/, "")}: ${q(t.value)}`));
lines.push("spacing:", ...tokens.spacing.tokens.map((t) => `  ${t.name}: ${q(t.value)}`));
const component = (name, props) => [`  ${name}:`, ...Object.entries(props).map(([k, v]) => `    ${k}: ${q(v)}`)];
lines.push("components:",
  ...component("button-primary", { backgroundColor: "{colors.accent}", textColor: "{colors.accent-fg}", typography: "{typography.body-strong}", rounded: "{rounded.md}", height: byName["control-md"], padding: "0 16px" }),
  ...component("button-secondary", { backgroundColor: "{colors.bg-elevated}", textColor: "{colors.text}", typography: "{typography.body-strong}", rounded: "{rounded.md}", height: byName["control-md"], padding: "0 16px" }),
  ...component("button-ghost", { textColor: "{colors.text-muted}", typography: "{typography.body-strong}", rounded: "{rounded.md}", height: byName["control-md"], padding: "0 16px" }),
  ...component("button-ghost-hover", { backgroundColor: "{colors.bg-hover}", textColor: "{colors.text}" }),
  ...component("input", { backgroundColor: "{colors.bg-elevated}", textColor: "{colors.text}", typography: "{typography.body}", rounded: "{rounded.md}", height: byName["control-md"], padding: "0 12px" }),
  ...component("card", { backgroundColor: "{colors.bg-elevated}", rounded: "{rounded.lg}", padding: "24px" }),
  ...component("badge", { backgroundColor: "{colors.accent-subtle}", textColor: "{colors.accent-text}", typography: "{typography.caption}", rounded: "{rounded.sm}", height: "24px", padding: "0 8px" }),
  ...component("side-panel", { backgroundColor: "{colors.bg-raised}", width: byName["panel-width"] }),
  "---", "");
const book = readFileSync(new URL("../../design/README.md", import.meta.url), "utf8");
const body = book.slice(book.indexOf("\n## ") + 1);
const head = `# Design System: ${tokens.name}\n\n<!-- Generated from design/tokens.json and design/README.md by frontend/scripts/build-tokens.mjs. Do not edit. -->\n\n`;
writeFileSync(new URL("../../DESIGN.md", import.meta.url), lines.join("\n") + head + body);
console.log(`tokens.css + DESIGN.md: ${themed.length} themed + ${flat.length} scale tokens, themes ${[first, ...others].join(", ")}`);

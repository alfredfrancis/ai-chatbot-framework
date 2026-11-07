// Generates src/tokens.css from design/tokens.json (the design system's tokens; edit those, not the CSS).
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
console.log(`tokens.css: ${themed.length} themed + ${flat.length} scale tokens, themes ${[first, ...others].join(", ")}`);

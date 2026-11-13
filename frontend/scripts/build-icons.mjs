// Renders the app icons in public/icons/ from the logo mark (design/README.md, Iconography) on the
// dark canvas, with colours from design/tokens.json. Run by hand when the mark changes:
//   node scripts/build-icons.mjs
// The PNGs are committed; the build does not need a browser.
import { mkdirSync, readFileSync } from "node:fs";
import { chromium } from "@playwright/test";

const root = new URL("..", import.meta.url).pathname;
const tokens = JSON.parse(readFileSync(new URL("../../design/tokens.json", import.meta.url), "utf8")).color.tokens;
const token = (name) => tokens.find((t) => t.name === name).value.dark;
const bg = token("bg");
const signal = token("brand-signal");
const WAVE = "4.4,12 6.3,15.8 8.2,8.4 10.1,15.8 12,8.4 13.9,15.8 15.8,8.4 17.7,15.8 19.6,12";

// mark = share of the icon the mark spans. Maskable icons keep it inside the 80% safe circle.
const ICONS = [
  { file: "icon-192.png", size: 192, mark: 0.72 },
  { file: "icon-512.png", size: 512, mark: 0.72 },
  { file: "icon-maskable-512.png", size: 512, mark: 0.56 },
  { file: "apple-touch-icon.png", size: 180, mark: 0.64 },
];

const out = `${root}public/icons/`;
mkdirSync(out, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ deviceScaleFactor: 1 });
for (const { file, size, mark } of ICONS) {
  const m = Math.round(size * mark);
  await page.setViewportSize({ width: size, height: size });
  await page.setContent(`<body style="margin:0;width:${size}px;height:${size}px;display:grid;place-items:center;background:${bg}">
    <svg width="${m}" height="${m}" viewBox="0 0 24 24" fill="none" stroke="${signal}" stroke-width="1.6"
      stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10.25"/><polyline points="${WAVE}"/></svg></body>`);
  await page.screenshot({ path: out + file, omitBackground: false });
  console.log(`public/icons/${file}`);
}
await browser.close();

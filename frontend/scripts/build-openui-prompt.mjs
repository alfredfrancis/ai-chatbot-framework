// Generates the openui skill's OpenUI Lang reference from the component library (src/openui/library.tsx):
// the agent learns exactly the components the web app can render, in chat replies and personal apps.
// Edit the library, not the generated file. CI checks the file is current.
import { existsSync, writeFileSync } from "node:fs";
import { createServer } from "vite";

const out = new URL("../../backend/acf/builtin_skills/openui/reference.md", import.meta.url);
if (!existsSync(new URL(".", out))) {
  console.log("openui/reference.md: no backend checkout here (e.g. the Docker web build), skipped");
  process.exit(0);
}
const server = await createServer({ configFile: false, logLevel: "error", server: { middlewareMode: true }, appType: "custom", optimizeDeps: { noDiscovery: true, include: [] } });
try {
  const { openuiPrompt } = await server.ssrLoadModule("/src/openui/library.tsx");
  const head = "<!-- Generated from frontend/src/openui/library.tsx by frontend/scripts/build-openui-prompt.mjs. Do not edit. -->\n\n";
  writeFileSync(out, head + openuiPrompt().trim() + "\n");
  console.log("openui/reference.md: written");
} finally {
  await server.close();
}

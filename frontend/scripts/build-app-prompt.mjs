// Generates the personal-apps skill's OpenUI Lang reference from the app component library
// (src/openui/library.tsx): the agent learns exactly the components the app page can render.
// Edit the library, not the generated file. CI checks the file is current.
import { existsSync, writeFileSync } from "node:fs";
import { createServer } from "vite";

const out = new URL("../../backend/acf/builtin_skills/personal-apps/openui.md", import.meta.url);
if (!existsSync(new URL(".", out))) {
  console.log("personal-apps/openui.md: no backend checkout here (e.g. the Docker web build), skipped");
  process.exit(0);
}
const server = await createServer({ configFile: false, logLevel: "error", server: { middlewareMode: true }, appType: "custom", optimizeDeps: { noDiscovery: true, include: [] } });
try {
  const { appPrompt } = await server.ssrLoadModule("/src/openui/library.tsx");
  const head = "<!-- Generated from frontend/src/openui/library.tsx by frontend/scripts/build-app-prompt.mjs. Do not edit. -->\n\n";
  writeFileSync(out, head + appPrompt().trim() + "\n");
  console.log("personal-apps/openui.md: written");
} finally {
  await server.close();
}

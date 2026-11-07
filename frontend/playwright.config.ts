import { defineConfig, devices } from "@playwright/test";

const root = new URL("..", import.meta.url).pathname;
const py = process.env.PYTHON ?? `${root}.venv/bin/python`;

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://127.0.0.1:8765",
    trace: "off",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `${py} -m tests.fakes.fake_llm --port 9100`,
      cwd: `${root}backend`,
      url: "http://127.0.0.1:9100/_requests",
      reuseExistingServer: !process.env.CI,
    },
    {
      command: `${py} -m tests.fakes.oauth_mcp --port 9200`,
      cwd: `${root}backend`,
      url: "http://127.0.0.1:9200/.well-known/oauth-authorization-server",
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "bash e2e/start-harbor.sh",
      url: "http://127.0.0.1:8765/api/health",
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});

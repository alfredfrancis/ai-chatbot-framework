import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { createInterface } from "node:readline";
import { expect, test } from "@playwright/test";
import { lastAssistant, nav, say, shot, signUp } from "./helpers";

const root = new URL("../..", import.meta.url).pathname;
const py = process.env.PYTHON ?? `${root}.venv/bin/python`;
const ACP_URL = "ws://127.0.0.1:8765/api/acp";

/** A stdio ACP client, the way an editor runs an agent: `python -m acf.acp_bridge`. */
function bridge(token: string) {
  const proc: ChildProcessWithoutNullStreams = spawn(py, ["-m", "acf.acp_bridge", "--url", ACP_URL], {
    cwd: `${root}backend`,
    env: { ...process.env, ACF_ACP_TOKEN: token },
  });
  const messages: Record<string, any>[] = [];
  const waiters: (() => void)[] = [];
  createInterface({ input: proc.stdout }).on("line", (line) => {
    messages.push(JSON.parse(line));
    waiters.splice(0).forEach((w) => w());
  });
  let stderr = "";
  proc.stderr.on("data", (d) => { stderr += String(d); });
  let id = 0;
  const call = async (method: string, params: Record<string, unknown>) => {
    const mid = ++id;
    proc.stdin.write(JSON.stringify({ jsonrpc: "2.0", id: mid, method, params }) + "\n");
    for (;;) {
      const hit = messages.find((m) => m.id === mid && !m.method);
      if (hit) return hit;
      await new Promise<void>((r) => waiters.push(r));
    }
  };
  const exited = new Promise<number | null>((r) => proc.on("exit", r));
  return { call, messages, exited, stderr: () => stderr, close: () => proc.stdin.end() };
}

test("web chat runs over ACP, and other apps connect with an access token", async ({ page }) => {
  const sockets: string[] = [];
  page.on("websocket", (ws) => sockets.push(ws.url()));
  await signUp(page);

  // The web chat itself speaks ACP over the WebSocket.
  await say(page, "run: echo web-$((2+3))");
  await expect(lastAssistant(page)).toHaveText(/Result: web-5/);
  expect(sockets.some((u) => u.endsWith("/api/acp"))).toBe(true);

  // External access is off until a token is created.
  await nav(page).getByRole("link", { name: "Settings" }).click();
  await expect(page.getByRole("heading", { name: "External apps" })).toBeVisible();
  await expect(page.getByTestId("acp-token-status")).toHaveText("No token. Other apps can't connect.");
  await expect(page.getByLabel("ACP address")).toHaveValue(ACP_URL);
  await page.getByRole("button", { name: "Create access token" }).click();
  const tokenBox = page.getByLabel("New access token");
  await expect(tokenBox).toHaveValue(/^acp_/);
  await expect(page.getByText("Copy it now. It won't be shown again.")).toBeVisible();
  await expect(page.getByTestId("acp-token-status")).toContainText("not used yet");
  await shot(page, "16-settings-external-apps");
  const token = await tokenBox.inputValue();

  // A third-party client (here: a stdio client through the bridge) uses the agent with the token.
  const client = bridge(token);
  try {
    const init = await client.call("initialize", { protocolVersion: 1, clientCapabilities: {} });
    expect(init.result.agentCapabilities.loadSession).toBe(true);
    const sid = (await client.call("session/new", { cwd: "/tmp", mcpServers: [] })).result.sessionId;
    const res = await client.call("session/prompt", { sessionId: sid, prompt: [{ type: "text", text: "run: echo from-editor" }] });
    expect(res.result.stopReason).toBe("end_turn");
    const chunks = client.messages.filter((m) => m.method === "session/update" && m.params.update.sessionUpdate === "agent_message_chunk");
    expect(chunks.at(-1)!.params.update.content.text).toContain("Result: from-editor");

    // The same conversation is a chat in the web app, replayed with session/load.
    await page.reload();
    await expect(page.getByTestId("acp-token-status")).toContainText("last used");
    await nav(page).getByRole("link", { name: "run: echo from-editor" }).click();
    await expect(page.getByTestId("user-msg")).toHaveText("run: echo from-editor");
    await expect(page.getByTestId("tool-step")).toContainText("Ran echo from-editor");
    await expect(lastAssistant(page)).toHaveText(/Result: from-editor/);
    await shot(page, "17-chat-from-external-app");
  } finally {
    client.close();
    await client.exited;
  }

  // Revoking the token turns external access off again.
  await nav(page).getByRole("link", { name: "Settings" }).click();
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Revoke token" }).click();
  await expect(page.getByTestId("acp-token-status")).toHaveText("No token. Other apps can't connect.");
  const refused = bridge(token);
  expect(await refused.exited).toBe(2);
  expect(refused.stderr()).toContain("refused the connection (403)");
});

test("reloading while the agent works follows the run over ACP", async ({ page }) => {
  await signUp(page);
  await say(page, "run: sleep 2; echo after-reload");
  await expect(page.getByTestId("tool-step")).toContainText("Ran sleep 2; echo after-reload");
  await page.reload();
  await expect(page.getByTestId("user-msg")).toHaveText("run: sleep 2; echo after-reload");
  await expect(page.getByText("Working").first()).toBeVisible();
  await expect(lastAssistant(page)).toHaveText(/Result: after-reload/);
  await expect(page.getByRole("button", { name: "Send" })).toBeVisible();
});

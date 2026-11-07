import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { lastAssistant, say, signUp } from "./helpers";

const echoServer = readFileSync(new URL("../../backend/tests/fakes/echo_mcp.py", import.meta.url));

test("add a local MCP server that runs in the sandbox and use its tools", async ({ page }) => {
  await signUp(page);
  await page.getByRole("link", { name: "Memory" }).click();
  await page.getByTestId("upload").setInputFiles({ name: "echo_mcp.py", mimeType: "text/x-python", buffer: echoServer });
  await expect(page.getByText("echo_mcp.py")).toBeVisible();

  await page.getByRole("link", { name: "Connections" }).click();
  await expect(page.getByText("No connections yet. Add one below.")).toBeVisible();
  await page.getByLabel("Configuration").fill(
    JSON.stringify({ mcpServers: { echo: { command: "python3", args: ["echo_mcp.py"] } } }, null, 2),
  );
  await page.getByRole("button", { name: "Save" }).click();
  const row = page.getByTestId("server-echo");
  await expect(row).toContainText("Runs in your sandbox · 3 tools");
  await expect(row).toContainText("Connected");
  await row.getByText("Show tools").click();
  await expect(row).toContainText("add — Add two numbers");

  await page.getByRole("link", { name: "Chats" }).click();
  await say(page, 'tool: mcp__echo__add {"a": 2, "b": 40}');
  await expect(page.getByTestId("tool-chip")).toContainText("Used echo · add");
  await expect(lastAssistant(page)).toHaveText("Result: 42");
});

test("invalid configuration is rejected with a clear message", async ({ page }) => {
  await signUp(page);
  await page.getByRole("link", { name: "Connections" }).click();
  await page.getByLabel("Configuration").fill('{"mcpServers": {"x": {}}}');
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("alert")).toContainText('"x" needs either a "command"');
});

test("sign in to a remote MCP server with OAuth in a popup", async ({ page }) => {
  await signUp(page);
  await page.getByRole("link", { name: "Connections" }).click();
  await page.getByLabel("Configuration").fill(
    JSON.stringify({ mcpServers: { notes: { url: "http://127.0.0.1:9200/mcp" } } }, null, 2),
  );
  await page.getByRole("button", { name: "Save" }).click();
  const row = page.getByTestId("server-notes");
  await expect(row).toContainText("Remote");

  const popupPromise = page.waitForEvent("popup");
  await row.getByRole("button", { name: "Sign in" }).click();
  const popup = await popupPromise;
  await expect(popup.getByRole("heading", { name: "Notes wants access" })).toBeVisible();
  await popup.getByRole("link", { name: "Allow access" }).click();
  await popup.waitForEvent("close");

  await expect(row).toContainText("Connected");
  await expect(row).toContainText("1 tool");
  await expect(row.getByRole("button", { name: "Sign out" })).toBeVisible();

  await page.getByRole("link", { name: "Chats" }).click();
  await say(page, "tool: mcp__notes__get_secret_note {}");
  await expect(lastAssistant(page)).toContainText("pineapple");

  await page.getByRole("link", { name: "Connections" }).click();
  await page.getByTestId("server-notes").getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByTestId("server-notes").getByRole("button", { name: "Sign in" })).toBeVisible();
});

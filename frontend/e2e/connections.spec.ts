import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { lastAssistant, nav, say, shot, signUp } from "./helpers";

const echoServer = readFileSync(new URL("../../backend/tests/fakes/echo_mcp.py", import.meta.url));

test("add a local MCP server that runs in the sandbox and use its tools", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Files" }).click();
  await page.getByTestId("upload").setInputFiles({ name: "echo_mcp.py", mimeType: "text/x-python", buffer: echoServer });
  await expect(page.getByRole("button", { name: /echo_mcp\.py/ })).toBeVisible();

  await nav(page).getByRole("link", { name: "Connections" }).click();
  await expect(page.getByText("No connections yet. Add one below.")).toBeVisible();
  await page.getByLabel("Configuration").fill(
    JSON.stringify({ mcpServers: { calculator: { command: "python3", args: ["echo_mcp.py"] } } }, null, 2),
  );
  await page.getByRole("button", { name: "Save" }).click();
  const row = page.getByTestId("server-calculator");
  await expect(row).toContainText("Runs in your sandbox · 3 tools");
  await expect(row).toContainText("Connected");
  await row.getByText("Show tools").click();
  await expect(row).toContainText("add — Add two numbers");

  await nav(page).getByRole("link", { name: "New chat" }).click();
  await say(page, 'tool: mcp__calculator__add {"a": 1234, "b": 4321}');
  await expect(page.getByTestId("tool-step")).toContainText("Used calculator · add");
  await expect(lastAssistant(page)).toHaveText("Result: 5555");
});

test("invalid configuration is rejected with a clear message", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Connections" }).click();
  await page.getByLabel("Configuration").fill('{"mcpServers": {"x": {}}}');
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("alert")).toContainText('"x" needs either a "command"');
});

test("sign in to a remote MCP server with OAuth in a popup", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Connections" }).click();
  await page.getByLabel("Configuration").fill(
    JSON.stringify({ mcpServers: { notes: { url: "http://127.0.0.1:9200/mcp" } } }, null, 2),
  );
  await page.getByRole("button", { name: "Save" }).click();
  const row = page.getByTestId("server-notes");
  await expect(row.getByRole("button", { name: "Sign in" })).toBeVisible();
  await shot(page, "08-connections-sign-in");

  const popupPromise = page.waitForEvent("popup");
  await row.getByRole("button", { name: "Sign in" }).click();
  const popup = await popupPromise;
  await expect(popup.getByRole("heading", { name: "Notes wants access" })).toBeVisible();
  await popup.getByRole("link", { name: "Allow access" }).click();
  await popup.waitForEvent("close");

  await expect(row).toContainText("Connected");
  await expect(row).toContainText("1 tool");
  await expect(row.getByRole("button", { name: "Sign out" })).toBeVisible();
  await shot(page, "09-connections-connected");

  await nav(page).getByRole("link", { name: "New chat" }).click();
  await say(page, "tool: mcp__notes__get_secret_note {}");
  await expect(lastAssistant(page)).toContainText("pineapple");

  await nav(page).getByRole("link", { name: "Connections" }).click();
  await page.getByTestId("server-notes").getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByTestId("server-notes").getByRole("button", { name: "Sign in" })).toBeVisible();
});

test("add a popular app in one click and sign in", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Connections" }).click();
  const apps = page.getByRole("region", { name: "Popular apps" });
  await expect(apps.getByRole("button", { name: "Add Linear" })).toBeVisible();
  await expect(apps.getByRole("button", { name: "Add Notion" })).toBeVisible();
  await shot(page, "09b-connections-popular-apps");

  await apps.getByRole("button", { name: "Add Notes" }).click();
  await expect(apps.getByTestId("preset-notes")).toContainText("Added");
  await expect(apps.getByRole("button", { name: "Add Notes" })).toHaveCount(0);
  await expect(page.getByLabel("Configuration")).toHaveValue(/"notes":\s*\{\s*"url": "http:\/\/127\.0\.0\.1:9200\/mcp"/);

  const row = page.getByTestId("server-notes");
  const popupPromise = page.waitForEvent("popup");
  await row.getByRole("button", { name: "Sign in" }).click();
  const popup = await popupPromise;
  await popup.getByRole("link", { name: "Allow access" }).click();
  await popup.waitForEvent("close");
  await expect(row).toContainText("Connected");
});

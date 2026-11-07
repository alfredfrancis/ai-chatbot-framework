import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";
import { lastAssistant, nav, say, shot, signUp } from "./helpers";

const echoServer = readFileSync(new URL("../../backend/tests/fakes/echo_mcp.py", import.meta.url));

async function openConnections(page: Page) {
  await nav(page).getByRole("link", { name: "Connections" }).click();
  await expect(page.getByRole("heading", { name: "Connections", level: 1 })).toBeVisible();
}

async function addRemote(page: Page, name: string, url: string) {
  await page.getByRole("button", { name: "Add connection" }).click();
  const form = page.getByRole("form", { name: "New connection" });
  await form.getByLabel("Name").fill(name);
  await form.getByLabel("Type").selectOption("http");
  await form.getByLabel("URL").fill(url);
  await form.getByRole("button", { name: "Add connection" }).click();
  await expect(form).toBeHidden();
}

test("add a local MCP server with the form and use its tools", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Files" }).click();
  await page.getByTestId("upload").setInputFiles({ name: "echo_mcp.py", mimeType: "text/x-python", buffer: echoServer });
  await expect(page.getByRole("button", { name: /echo_mcp\.py/ })).toBeVisible();

  await openConnections(page);
  await expect(page.getByText("No connections yet.")).toBeVisible();
  await page.getByRole("button", { name: "Add connection" }).click();
  const form = page.getByRole("form", { name: "New connection" });
  await form.getByLabel("Name").fill("calculator");
  await expect(form.getByLabel("Type")).toHaveValue("stdio");
  await form.getByLabel("Command").fill("python3");
  await form.getByLabel("Arguments").fill("echo_mcp.py");
  await form.getByLabel("Environment variables").fill("GREETING=hello");
  await shot(page, "07-connections-form");
  await form.getByRole("button", { name: "Add connection" }).click();

  const row = page.getByTestId("server-calculator");
  await expect(row).toContainText("Runs in your sandbox · 3 tools");
  await expect(row).toContainText("Connected");
  await row.getByText("Show tools").click();
  await expect(row).toContainText("add — Add two numbers");

  // The form wrote Claude-Desktop-style JSON, visible in the JSON view.
  await page.getByRole("button", { name: "JSON" }).click();
  const json = JSON.parse(await page.getByLabel("Configuration (JSON)").inputValue());
  expect(json.mcpServers.calculator).toEqual({ command: "python3", args: ["echo_mcp.py"], env: { GREETING: "hello" } });
  await page.getByRole("button", { name: "Form" }).click();

  await nav(page).getByRole("link", { name: "New chat" }).click();
  await say(page, 'tool: mcp__calculator__add {"a": 1234, "b": 4321}');
  await expect(page.getByTestId("tool-step")).toContainText("Used calculator · add");
  await expect(lastAssistant(page)).toHaveText("Result: 5555");
});

test("edit, turn off, rename and delete a connection", async ({ page }) => {
  await signUp(page);
  await openConnections(page);
  await addRemote(page, "notes", "http://127.0.0.1:9200/mcp");
  await expect(page.getByTestId("server-notes")).toContainText("Needs sign-in");

  await page.getByRole("button", { name: "Edit notes" }).click();
  const form = page.getByRole("form", { name: "Edit notes" });
  await expect(form.getByLabel("URL")).toHaveValue("http://127.0.0.1:9200/mcp");
  await form.getByLabel("Name").fill("journal");
  await form.getByLabel("Headers").fill("X-Api-Key: secret");
  await page.emulateMedia({ colorScheme: "light" });
  await page.setViewportSize({ width: 390, height: 844 });
  await shot(page, "07c-connections-edit-phone-light");
  await form.getByRole("switch", { name: "Turned on" }).uncheck();
  await form.getByRole("button", { name: "Save changes" }).click();
  await expect(form).toBeHidden();

  await expect(page.getByTestId("server-notes")).toHaveCount(0);
  await expect(page.getByTestId("server-journal")).toContainText("Off");
  await page.getByRole("button", { name: "JSON" }).click();
  expect(JSON.parse(await page.getByLabel("Configuration (JSON)").inputValue()).mcpServers).toEqual({
    journal: { url: "http://127.0.0.1:9200/mcp", headers: { "X-Api-Key": "secret" }, enabled: false },
  });
  await page.getByRole("button", { name: "Form" }).click();

  await page.getByRole("button", { name: "Delete journal" }).click();
  await page.getByRole("button", { name: "Confirm delete journal" }).click();
  await expect(page.getByText("No connections yet.")).toBeVisible();
});

test("form validation errors are shown", async ({ page }) => {
  await signUp(page);
  await openConnections(page);
  await page.getByRole("button", { name: "Add connection" }).click();
  const form = page.getByRole("form", { name: "New connection" });
  await form.getByLabel("Name").fill("bad name");
  await form.getByLabel("Command").fill("npx");
  await form.getByRole("button", { name: "Add connection" }).click();
  await expect(form.getByRole("alert")).toContainText("may only use letters");

  await form.getByLabel("Name").fill("ok");
  await form.getByLabel("Environment variables").fill("not a pair");
  await form.getByRole("button", { name: "Add connection" }).click();
  await expect(form.getByRole("alert")).toContainText("Environment variables line 1: use NAME=value");
});

test("JSON view: invalid configuration is rejected with a clear message", async ({ page }) => {
  await signUp(page);
  await openConnections(page);
  await page.getByRole("button", { name: "JSON" }).click();
  await page.getByLabel("Configuration (JSON)").fill('{"mcpServers": {"x": {}}}');
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("alert")).toContainText('"x" needs either a "command"');

  await page.getByLabel("Configuration (JSON)").fill(JSON.stringify({ mcpServers: { linear: { url: "https://mcp.example.com/mcp" } } }));
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("status")).toHaveText("Saved");
  await shot(page, "07b-connections-json");
  await page.getByRole("button", { name: "Form" }).click();
  await expect(page.getByTestId("server-linear")).toBeVisible();
});

test("sign in to a remote MCP server with OAuth in a popup", async ({ page }) => {
  await signUp(page);
  await openConnections(page);
  await addRemote(page, "notes", "http://127.0.0.1:9200/mcp");
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

  await openConnections(page);
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

  const row = page.getByTestId("server-notes");
  const popupPromise = page.waitForEvent("popup");
  await row.getByRole("button", { name: "Sign in" }).click();
  const popup = await popupPromise;
  await popup.getByRole("link", { name: "Allow access" }).click();
  await popup.waitForEvent("close");
  await expect(row).toContainText("Connected");

  await page.getByRole("button", { name: "JSON", exact: true }).click();
  const json = JSON.parse(await page.getByLabel("Configuration (JSON)").inputValue());
  expect(json.mcpServers.notes).toEqual({ url: "http://127.0.0.1:9200/mcp" });
});

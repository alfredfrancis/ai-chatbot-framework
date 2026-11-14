import { expect, test } from "@playwright/test";
import { lastAssistant, nav, openSteps, say, shot, signUp } from "./helpers";

test("create, run, pause and delete a recurring task", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Tasks" }).click();
  await expect(page.getByRole("heading", { name: "Put your agent on a schedule" })).toBeVisible();
  await page.getByRole("button", { name: "New task" }).click();
  await page.getByLabel("Name").fill("Morning check");
  await page.getByLabel("What should the agent do?").fill("run: echo task-ran");
  await page.getByLabel("Repeat").selectOption("weekdays");
  await page.getByLabel("At", { exact: true }).fill("07:30");
  await shot(page, "10-task-form");
  await page.getByRole("button", { name: "Create task" }).click();

  const row = page.getByTestId("task-Morning check");
  await expect(row).toContainText("Every weekday at 07:30");
  await expect(row).toContainText("Next");

  await row.getByRole("button", { name: "Run now" }).click();
  await expect(page).toHaveURL(/\/c\/\d+$/);
  await expect(page.locator(".topbar .here")).toContainText("Morning check ·");
  await expect(lastAssistant(page)).toContainText("Result: task-ran");

  await nav(page).getByRole("link", { name: "Tasks" }).click();
  await expect(row).toContainText("View result");
  await shot(page, "11-tasks");
  await row.getByRole("switch", { name: "Morning check enabled" }).click();
  await expect(row).toContainText("Paused");

  await row.getByRole("button", { name: "More actions for Morning check" }).click();
  await page.getByRole("menuitem", { name: "Delete task" }).click();
  await page.getByRole("menuitem", { name: "Yes, delete this task" }).click();
  await expect(row).toHaveCount(0);
});

test("a task runs on its schedule", async ({ page }) => {
  test.setTimeout(150_000); // the next "* * * * *" run can be up to a minute away
  await signUp(page);
  await nav(page).getByRole("link", { name: "Tasks" }).click();
  await page.getByRole("button", { name: "New task" }).click();
  await page.getByLabel("Name").fill("Every minute");
  await page.getByLabel("What should the agent do?").fill("scheduled hello");
  await page.getByLabel("Repeat").selectOption("custom");
  await page.getByLabel("Cron expression").fill("* * * * *");
  await page.getByRole("button", { name: "Create task" }).click();
  const row = page.getByTestId("task-Every minute");
  await expect(row).toContainText("Custom (* * * * *)");
  await expect(async () => {
    await page.reload();
    await expect(row.getByRole("link", { name: "View result" })).toBeVisible({ timeout: 1000 });
  }).toPass({ timeout: 100_000, intervals: [3000] });
  await row.getByRole("link", { name: "View result" }).click();
  await expect(lastAssistant(page)).toHaveText("Echo: scheduled hello");
});

test("the agent sets up a recurring task from the chat", async ({ page }) => {
  await signUp(page);
  const args = { name: "Weekly digest", prompt: "run: echo digest", schedule: "0 9 * * 1", timezone: "UTC" };
  await say(page, `tool: mcp_call ${JSON.stringify({ server: "system", tool: "create_task", arguments: args })}`);
  await expect(lastAssistant(page)).toContainText('"name": "Weekly digest"');
  await openSteps(page);
  await expect(page.getByTestId("tool-step")).toContainText("Used system · create_task");
  await shot(page, "12-agent-created-task");

  await nav(page).getByRole("link", { name: "Tasks" }).click();
  const row = page.getByTestId("task-Weekly digest");
  await expect(row).toContainText("Next");
  await row.getByRole("button", { name: "Run now" }).click();
  await expect(lastAssistant(page)).toContainText("Result: digest");
});

test("a one-off task runs once at its time and then shows as done", async ({ page }) => {
  test.setTimeout(180_000); // its time is the start of a minute up to two minutes away
  await signUp(page);
  await nav(page).getByRole("link", { name: "Tasks" }).click();
  await page.getByRole("button", { name: "New task" }).click();
  await page.getByLabel("Name").fill("Reminder");
  await page.getByLabel("What should the agent do?").fill("one-off hello");
  await page.getByLabel("Repeat").selectOption("once");
  const at = new Date(Date.now() + 61_000);
  const pad = (n: number) => String(n).padStart(2, "0");
  const local = `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}T${pad(at.getHours())}:${pad(at.getMinutes())}`;
  await page.getByLabel("On", { exact: true }).fill(local);
  await shot(page, "12b-one-off-task-form");
  await page.getByRole("button", { name: "Create task" }).click();

  const row = page.getByTestId("task-Reminder");
  await expect(row).toContainText("Once on");
  await expect(row).toContainText("Next");
  await expect(async () => {
    await page.reload();
    await expect(row.getByText("Done", { exact: true })).toBeVisible({ timeout: 1000 });
  }).toPass({ timeout: 150_000, intervals: [3000] });
  await expect(row.getByRole("switch")).toHaveCount(0);
  await expect(row).not.toContainText("Next");
  await shot(page, "12c-one-off-task-done");
  await row.getByRole("link", { name: "View result" }).click();
  await expect(lastAssistant(page)).toHaveText("Echo: one-off hello");
});

test("the agent schedules a one-off reminder from the chat", async ({ page }) => {
  await signUp(page);
  const args = { name: "Call mum", prompt: "Remind me to call mum", run_at: "2099-01-01T17:00", timezone: "UTC" };
  await say(page, `tool: mcp_call ${JSON.stringify({ server: "system", tool: "create_task", arguments: args })}`);
  await expect(lastAssistant(page)).toContainText('"run_at": "2099-01-01T17:00:00Z"');
  await nav(page).getByRole("link", { name: "Tasks" }).click();
  await expect(page.getByTestId("task-Call mum")).toContainText("Once on");
});

test("a task runs on a model of its own", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Tasks" }).click();
  await page.getByRole("button", { name: "New task" }).click();
  await page.getByLabel("Name").fill("Hourly digest");
  await page.getByLabel("What should the agent do?").fill("show model");
  await page.getByLabel("Repeat").selectOption("hourly");
  const model = page.getByLabel("Model", { exact: true });
  await expect(model).toHaveValue("");
  await expect(model.locator("option").first()).toHaveText("Default (Claude Opus 5.5)");
  await model.selectOption({ label: "Claude Sonnet 5.5" });
  await shot(page, "12d-task-model");
  await page.getByRole("button", { name: "Create task" }).click();

  const row = page.getByTestId("task-Hourly digest");
  await expect(row).toContainText("Every hour · Claude Sonnet 5.5");
  await row.getByRole("button", { name: "Run now" }).click();
  await expect(lastAssistant(page)).toHaveText("Model: claude-sonnet-5-5");
  await expect(page.getByLabel("Model", { exact: true })).toHaveValue("anthropic:claude-sonnet-5-5");

  // A new chat is still on the default model.
  await nav(page).getByRole("link", { name: "New chat" }).click();
  await expect(page.getByLabel("Model", { exact: true })).toHaveValue("anthropic:claude-opus-5-5");
});

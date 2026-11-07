import { expect, test } from "@playwright/test";
import { lastAssistant, nav, shot, signUp } from "./helpers";

test("create, run, pause and delete a recurring task", async ({ page }) => {
  await signUp(page);
  await nav(page).getByRole("link", { name: "Tasks" }).click();
  await expect(page.getByText(/No tasks yet/)).toBeVisible();
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
  await expect(page.locator(".chat-header")).toContainText("Morning check ·");
  await expect(lastAssistant(page)).toContainText("Result: task-ran");

  await nav(page).getByRole("link", { name: "Tasks" }).click();
  await expect(row).toContainText("View result");
  await shot(page, "11-tasks");
  await row.getByRole("switch", { name: "Morning check enabled" }).click();
  await expect(row).toContainText("Paused");

  page.once("dialog", (d) => d.accept());
  await row.getByRole("button", { name: "Delete Morning check" }).click();
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

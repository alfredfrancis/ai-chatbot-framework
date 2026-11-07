import { expect, test } from "@playwright/test";
import { lastAssistant, say, shot, signUp } from "./helpers";

const bash = (command: string, background = false) => `tool: bash ${JSON.stringify(background ? { command, background } : { command })}`;

test("independent commands run at the same time", async ({ page }) => {
  await signUp(page);
  await say(page, [bash("sleep 3; echo one"), bash("sleep 3; echo two"), bash("sleep 3; echo three")].join("\n"));
  const steps = page.getByTestId("tool-step");
  await expect(steps).toHaveCount(3);
  await expect(page.getByLabel("Working", { exact: true })).toHaveCount(3); // all three are running at once
  await shot(page, "06-parallel-commands");
  await expect(steps.locator(".ok")).toHaveCount(3, { timeout: 15_000 });
  await expect(lastAssistant(page)).toHaveText(/^Result: /);
});

test("a background command reports back and the agent picks it up", async ({ page }) => {
  await signUp(page);
  await say(page, bash("sleep 4; echo bg-finished", true));
  const step = page.getByTestId("tool-step");
  await expect(lastAssistant(page)).toHaveText(/^Result: Started in the background/);
  await expect(step).toContainText("In background");
  await expect(step.getByLabel("Running in background")).toBeVisible();
  await expect(page.getByText("Commands are running in the background")).toBeVisible();
  await shot(page, "07-background-command");

  // The agent is free in the meantime.
  await say(page, "hello meanwhile");
  await expect(lastAssistant(page)).toHaveText("Echo: hello meanwhile");
  await expect(step.first()).toContainText("In background");

  // When it finishes, the step completes and the agent reads the output by itself.
  await expect(lastAssistant(page)).toHaveText(/^Background done: /, { timeout: 15_000 });
  await expect(step.first().locator(".ok")).toBeVisible();
  await expect(step.first()).toContainText(/\d\.\ds/);
  await step.first().click();
  await expect(page.locator(".step-output").first()).toContainText("bg-finished");
  await expect(page.getByRole("button", { name: "Send" })).toBeVisible();
  await shot(page, "08-background-finished");

  await page.reload();
  await expect(page.getByTestId("user-msg")).toHaveCount(2);
  await expect(page.getByTestId("tool-step").first().locator(".ok")).toBeVisible();
  await expect(lastAssistant(page)).toHaveText(/^Background done: /);
});

test("stop ends background commands", async ({ page }) => {
  await signUp(page);
  await say(page, bash("sleep 60", true));
  await expect(lastAssistant(page)).toHaveText(/^Result: Started in the background/);
  await page.getByRole("button", { name: "Stop" }).click();
  await expect(page.getByTestId("tool-step").locator(".fail")).toBeVisible();
  await expect(page.getByRole("button", { name: "Send" })).toBeVisible();
});

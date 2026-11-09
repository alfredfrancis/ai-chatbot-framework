import { expect, test } from "@playwright/test";
import { lastAssistant, say, shot, signUp } from "./helpers";

const agent = (description: string, prompt: string, model?: string) =>
  `tool: agent ${JSON.stringify(model ? { description, prompt, model } : { description, prompt })}`;

test("sub-agents work side by side, each on its own model, and report back", async ({ page }) => {
  await signUp(page);
  await say(page, [
    agent("Check the sales file", "run: sleep 3; echo sales-ok"),
    agent("Check the costs file", "run: sleep 3; echo costs-ok", "fast"),
    agent("Name your model", "show model", "claude-sonnet-5-5"),
  ].join("\n"));
  const steps = page.getByTestId("tool-step");
  await expect(steps).toHaveCount(3);
  await expect(steps.nth(0)).toContainText("Sub-agent");
  await expect(steps.nth(0)).toContainText("Check the sales file");
  // Two are still working at the same time, and each shows what it is doing right now.
  await expect(page.getByLabel("Working", { exact: true })).toHaveCount(2);
  await expect(steps.nth(0)).toContainText("Ran sleep 3; echo sales-ok");
  await expect(steps.nth(1)).toContainText("Ran sleep 3; echo costs-ok");
  await shot(page, "09-sub-agents-working");

  await expect(steps.locator(".ok")).toHaveCount(3, { timeout: 20_000 });
  await expect(lastAssistant(page)).toHaveText(/^Result: /);
  await expect(steps.nth(2)).toContainText("claude-sonnet-5-5");

  // Opening a sub-agent shows its model, its steps and its report.
  await steps.nth(0).click();
  const details = page.getByRole("group", { name: "Sub-agent: Check the sales file" });
  await expect(details.getByRole("listitem")).toHaveText(["Ran sleep 3; echo sales-ok"]);
  await expect(details).toContainText("1 step");
  await expect(details.locator(".step-output")).toContainText("Result: sales-ok");
  await steps.nth(2).click();
  await expect(page.getByRole("group", { name: "Sub-agent: Name your model" }).locator(".step-output")).toHaveText("Model: claude-sonnet-5-5");
  await shot(page, "10-sub-agents-done");

  // A sub-agent starts fresh: none of this chat reaches it.
  await say(page, agent("What do you know", "show messages"));
  await expect(steps).toHaveCount(4);
  await expect(steps.nth(3).locator(".ok")).toBeVisible();
  await steps.nth(3).click();
  await expect(page.getByRole("group", { name: "Sub-agent: What do you know" }).locator(".step-output")).toHaveText("Messages: show messages");

  // After a reload the steps and reports are still there.
  await page.reload();
  await expect(page.getByTestId("tool-step")).toHaveCount(4);
  await page.getByTestId("tool-step").nth(1).click();
  const again = page.getByRole("group", { name: "Sub-agent: Check the costs file" });
  await expect(again.getByRole("listitem")).toHaveText(["Ran sleep 3; echo costs-ok"]);
  await expect(again.locator(".step-output")).toContainText("Result: costs-ok");
});

test("stop ends the sub-agents too", async ({ page }) => {
  await signUp(page);
  await say(page, [agent("Slow one", "run: sleep 60"), agent("Slow two", "run: sleep 60")].join("\n"));
  await expect(page.getByLabel("Working", { exact: true })).toHaveCount(2);
  await page.getByRole("button", { name: "Stop" }).click();
  await expect(page.getByTestId("tool-step").locator(".fail")).toHaveCount(2);
  await expect(page.getByRole("button", { name: "Send" })).toBeVisible();
  await say(page, "hello again");
  await expect(lastAssistant(page)).toHaveText("Echo: hello again");
});
